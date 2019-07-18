from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
# from goods.models import GoogsSKU
# from user.models import Address
from django.conf import settings
from order.models import OrderInfo, OrderGoods
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from django.http import JsonResponse
from datetime import datetime
from django.db import transaction
from alipay import AliPay
import os
import time
# Create your views here.

class OrderPlaceView(LoginRequiredMixin, View):
    '''提交订单页面'''
    def post(self, request):
        user = request.user
        # 获取参数sku_ids
        sku_ids = request.POST.getlist('sku_ids')

        # 校验参数
        if not sku_ids:
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        skus = []
        total_count = 0
        total_price = 0
        # 遍历获取用户要购买的商品的信息
        for sku_id in sku_ids:
            sku = GoogsSKU.objects.get(id = sku_id)
            # 获取用户购买的商品数量
            count = conn.hget(cart_key, sku_id)
            amount = sku.price*int(count)
            sku.count = count
            sku.amount = amount
            total_count += count
            total_price += amount
            skus.append(sku)

        # 运费:实际开发属于一个子系统
        transit_price = 10
        # 获取地址
        addrs= Address.objects.filter(user=user)
        # 计算实际的金额　
        total_pay = total_price + transit_price
        sku_ids = ','.join(skus)
        context = {
            'skus':skus,
            'addrs':addrs,
            'total_price':total_price,
            'total_pay':total_pay,
            'transit_price':transit_price,
            'total_count':total_count,
            'sku_ids':sku_ids
        }
        return render(request, 'place_order.html', context)

class OrderCommitView(View):
    # 通过装饰器实现ＭｙＳＱＬ事务
    @transaction.atomic
    def post(self, request):
        # 判断是否登录
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})
        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')

        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res':1, 'errmsg':'数据不完整'})

        # 校验支付方式
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res':2, 'errmsg':'支付方式错误'})

        # 校验地址
        try:
            addr = Address.objects.get(id= addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res':3, 'errmsg':'地址不存在'})

        # 创建订单业务
        # 组织参数
        # 订单ＩＤ
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        # 运费
        transit_price = 10
        # 总数目总金额
        total_count = 0
        total_price = 0

        # 设置保存点
        save_id = transaction.savepoint()
        try:
            # 向订单表中添加一条数据
            order = OrderInfo.objects.create(order_id=order_id,
                                     user=user,
                                     addr = addr,
                                     pay_method=pay_method,
                                     transit_price= transit_price,
                                     total_count=total_count,
                                     total_price = total_price
                                     )
            # 向订单商品表中添加对应的数据
            sku_ids = sku_ids.split(',')
            conn = get_redis_connection('default')
            cart_key = 'cart_%d'%user.id

            for sku_id in sku_ids:
                for i in range(3):
                    try:
                        sku = GoogsSKU.objects.get(id=sku_id)
                    except GoogsSKU.DoesNotExist:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':4, 'errmsg':'商品不存在'})
                    # 从ｒｅｄｉｓ中获取要购买的数量
                    count = conn.hget(cart_key, sku_id)

                    # 判断商品库存
                    if int(count) > sku.stock:
                        transaction.savepoint_rollback(save_id)
                        return JsonResponse({'res':6, 'errmsg':'库存不足'})

                    # 更新库存数量和销量
                    orgin_stock = sku.stock
                    new_stock = orgin_stock - int(count)
                    new_sales = sku.sales + int(count)
                    # 返回受影响的行数
                    res = GoogsSKU.objects.filter(id=sku_id, stock=orgin_stock).update(stock=new_stock, sales= new_sales)
                    if res == 0:
                        if i == 2:
                            transaction.savepoint_rollback(save_id)
                            return JsonResponse({'res':7, 'msg':'下单失败'})
                        continue
                    # 向订单商品表中添加数据
                    OrderGoods.objects.create(order=order, sku=sku, count=count, price=sku.price)

                    # 累加计算订单商品的数量和价格
                    amount = sku.price*int(count)
                    total_count += int(count)
                    total_price += amount
                    # 成功跳出循环
                    break

            # 更新订单信息表中的总数量和总价格
            order.total_count = total_count
            order.total_price = total_price
            order.save()
        except Exception as e:
            transaction.savepoint_rollback(save_id)
            return JsonResponse({'res':7, 'msg':'下单失败'})

        # 提交事务
        transaction.savepoint_commit(save_id)
        # 清除用户购物车中对应的记录
        conn.hdel(cart_key, *sku_ids)

        # 返回应答
        return JsonResponse({'res':5, 'msg':'创建成功'})

class OrderPayView(View):
    '''订单支付'''
    def post(self, request):
        '''订单支付ＡＪＡＸｐｏｓｔ'''
        user = request.user
        # 校验登录
        if not user.is_authenticated:
            return JsonResponse({'res':0, 'errmsg':'用户未登陆'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res':1, 'errmsg':'无效订单ＩＤ'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user= user,
                                          pay_method = 3,
                                          order_status = 1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res':2, 'errmsg':'订单有误'})
        # 业务处理：使用python sdk 调用支付宝的支付借口
        # 初始化
        alipay = AliPay(
            appid = '2016100200643435',  # 应用ＩＤ
            app_notify_url=None, # 默认回调ｕｒｌ
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type='RSA2',
            debug=True # 默认为False, 沙箱为True
        )
        total_pay = order.total_price + order.transit_price
        # 调用支付接口
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no= order_id,# 订单编号
            total_amount= str(total_pay),# 价格
            subject = '天天生鲜%s'%order_id, # 标题
            return_url=None,
            notify_url=None
        )

        # 返回应答
        pay_url = 'https://openapi.alipaydev.com/gateway.do?'+order_string
        return JsonResponse({'res':3, 'pay_url':pay_url})

class CheckPayView(View):
    def post(self, request):
        '''查询支付结果'''
        user = request.user
        # 校验登录
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登陆'})
        # 接收参数
        order_id = request.POST.get('order_id')
        # 校验参数
        if not order_id:
            return JsonResponse({'res': 1, 'errmsg': '无效订单ＩＤ'})
        try:
            order = OrderInfo.objects.get(order_id=order_id,
                                          user=user,
                                          pay_method=3,
                                          order_status=1)
        except OrderInfo.DoesNotExist:
            return JsonResponse({'res': 2, 'errmsg': '订单有误'})
        # 业务处理：使用python sdk 调用支付宝的支付借口
        # 初始化
        alipay = AliPay(
            appid='2016100200643435',  # 应用ＩＤ
            app_notify_url=None,  # 默认回调ｕｒｌ
            app_private_key_path=os.path.join(settings.BASE_DIR, 'apps/order/app_private_key.pem'),
            alipay_public_key_path=os.path.join(settings.BASE_DIR, 'apps/order/alipay_public_key.pem'),
            sign_type='RSA2',
            debug=True  # 默认为False, 沙箱为True
        )
        # 调用交易查询接口
        while True:
            response = alipay.api_alipay_trade_query(out_trade_no=order_id)
            # response = {
            #     "alipay_trade_query_response": {
            #         "trade_no": "2017032121001004070200176844", # 支付宝交易号
            #         "code": "10000", # 借口调用是否成功
            #         "invoice_amount": "20.00",
            #         "open_id": "20880072506750308812798160715407",
            #         "fund_bill_list": [
            #             {
            #                 "amount": "20.00",
            #                 "fund_channel": "ALIPAYACCOUNT"
            #             }
            #         ],
            #         "buyer_logon_id": "csq***@sandbox.com",
            #         "send_pay_date": "2017-03-21 13:29:17",
            #         "receipt_amount": "20.00",
            #         "out_trade_no": "out_trade_no15",
            #         "buyer_pay_amount": "20.00",
            #         "buyer_user_id": "2088102169481075",
            #         "msg": "Success",
            #         "point_amount": "0.00",
            #         "trade_status": "TRADE_SUCCESS", # 支付结果
            #         "total_amount": "20.00"
            # }
            code = response.get('code')
            if code == '10000' and response.get('trade_status') == "TRADE_SUCCESS":
                # 支付成功
                # 获取支付宝交易号
                trade_no = response.get('trade_no')
                # 更新订单状态
                order.trade_no = trade_no
                order.order_status = 4
                order.save()
                return JsonResponse({'res': 3, 'errmsg': '支付成功'})
            elif code == '40004' or code == '10000' and response.get('trade_status') == "WAIT_BUYER_PAY":
                # 等待买家付款
                time.sleep(5)
                continue
            else:
                # 支付出错
                return JsonResponse({'res': 4, 'errmsg': '支付失败'})

class CommentView(LoginRequiredMixin, View):
    """订单评论"""
    def get(self, request, order_id):
        """提供评论页面"""
        user = request.user

        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        # 根据订单的状态获取订单的状态标题
        order.status_name = OrderInfo.ORDER_STATUS[order.order_status]

        # 获取订单商品信息
        order_skus = OrderGoods.objects.filter(order_id=order_id)
        for order_sku in order_skus:
            # 计算商品的小计
            amount = order_sku.count*order_sku.price
            # 动态给order_sku增加属性amount,保存商品小计
            order_sku.amount = amount
        # 动态给order增加属性order_skus, 保存订单商品信息
        order.order_skus = order_skus

        # 使用模板
        return render(request, "order_comment.html", {"order": order})

    def post(self, request, order_id):
        """处理评论内容"""
        user = request.user
        # 校验数据
        if not order_id:
            return redirect(reverse('user:order'))

        try:
            order = OrderInfo.objects.get(order_id=order_id, user=user)
        except OrderInfo.DoesNotExist:
            return redirect(reverse("user:order"))

        # 获取评论条数
        total_count = request.POST.get("total_count")
        total_count = int(total_count)

        # 循环获取订单中商品的评论内容
        for i in range(1, total_count + 1):
            # 获取评论的商品的id
            sku_id = request.POST.get("sku_%d" % i) # sku_1 sku_2
            # 获取评论的商品的内容
            content = request.POST.get('content_%d' % i, '') # cotent_1 content_2 content_3
            try:
                order_goods = OrderGoods.objects.get(order=order, sku_id=sku_id)
            except OrderGoods.DoesNotExist:
                continue

            order_goods.comment = content
            order_goods.save()

        order.order_status = 5 # 已完成
        order.save()

        return redirect(reverse("user:order", kwargs={"page": 1}))
#
#





