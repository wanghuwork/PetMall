from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from django_redis import get_redis_connection
# from utils.mixin import LoginRequiresMixin
# Create your views here.

class CartAddView(View):
    '''购物车记录添加'''
    def post(self, request):
        '''购物车记录的添加'''
        user = request.user
        if not user.is_authenticated():
            return JsonResponse({'res':0, 'errmsg':'请先登录账户'})
        # 接收数据
        sku_id = request.POST.get('shu_id')
        count = request.POST.get('count')
        # 数据校验
        if not all([sku_id, count]):
            return JsonResponse({'res':1, 'errmsg':'数据不完整'})
        #　商品数量是否有效
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res':2, 'errmsg':'商品数目出错'})
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id = sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res':3, 'errmsg':'商品不存在'})

        # 业务处理：添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        # 先尝试获取sku_id的值　　hget
        # 如果不存在函数返回Ｎｏｎｅ
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            # 累加
            count += int(cart_count)
        # 校验商品库存
        if count > sku.stock:
            return JsonResponse({'res':4, 'errmsg':'商品库存不足'})
        # 设置hash中的值 如果商品已经存在更新数据，如果不存在则是添加
        conn.hset(cart_key, sku_id, count)

        # 计算用户购物车中的条目数
        total_count = conn.hlen(cart_key)
        # 返回应答
        return JsonResponse({'res':5, 'total_count':total_count, 'message':'添加成功'})

class CartUpdateView(View):
    '''更新购物车记录'''
    def post(self, request):
        user = request.user
        # 判断用户是否登录
        if not user.is_authenticated:
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})
        # 接收数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 校验数据
        if not all([sku_id, count]):
            return JsonResponse({'res':1, 'errmsg':'数据不完整'})
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res':2, 'errmsg':'商品数目有误'})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res':3, 'errmsg':'商品不存在'})

        # 业务处理,更新购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        # 校验库存
        if count > sku.stock:
            return JsonResponse({'res':4, 'errmsg':'商品库存不足'})
        conn.hset(cart_key, sku_id, count)
        # 计算总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)

        return JsonResponse({'res':5, 'message':'更新成功', 'total_count':total_count})

class CartInfoView(LoginRequiresMixin, View):
    '''购物车页面显示'''
    def get(self, request):
        # 获取登录用户
        user = request.user
        # 获取用户购物车中商品的信息
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id
        cart_dict = conn.hgetall(cart_key)
        # 保存用户购物车中的商品数目和价格
        total_price = 0
        total_count = 0
        skus = []
        for sku_id, count in cart_dict.items():
            sku = GoodsSKU.objects.get(id=sku_id)
            amout = sku.price*int(count)
            sku.amout = amout
            sku.count = count
            skus.append(sku)
            total_count += count
            total_price += amout
        context = {
            'skus':skus,
            'total_price':total_price,
            'total_count':total_count
        }
        return render(request, 'cart.html', context)

class CartDeleteView(View):
    '''购物车商品删除'''
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res':0, 'errmsg':'用户未登录'})
        sku_id = request.POST.get('sku_id')

        if not sku_id:
            return JsonResponse({'res':1, 'errmsg':'无效的商品ＩＤ'})

        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except GoodsSKU.DoesNotExist:
            return JsonResponse({'res':2, 'errmsg':'商品不存在'})
        # 业务处理，删除记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d'%user.id

        # 删除
        conn.hdel(cart_key, sku_id)

        # 计算总件数
        total_count = 0
        vals = conn.hvals(cart_key)
        for val in vals:
            total_count += int(val)
        return JsonResponse({'res':3, 'msg':'商品删除成功', 'total_count':total_count})









