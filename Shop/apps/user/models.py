from django.db import models
from django.contrib.auth.models import AbstractUser
from db.base_model import BaseModel


# Create your models here.

class UserInfo(AbstractUser, BaseModel):
    '''用户模型类'''

    class Meta:
        db_table = 'userinfo'
        verbose_name = '用户表'
        verbose_name_plural = verbose_name

class AddrManager(models.Manager):
    '''地址模型管理器类'''
    # 1.改变原有查询的结果集:all()
    # 2.封装方法:用户操作模型类对应的数据表(增删改查)
    def get_default_address(self, user):
        '''获取用户默认收货地址'''
        # self.model:获取self对象所在的模型类
        try:
            address = self.get(user=user, is_default=True)  # models.Manager
        except self.model.DoesNotExist:
            # 不存在默认收货地址
            address = None

        return address



class AddressManager(models.Model):
    user = models.ForeignKey('UserInfo', verbose_name='所属用户', on_delete=True)
    recipients = models.CharField(max_length=20, verbose_name='收件人')
    address = models.CharField(max_length=400, verbose_name='收件地址')
    postcode = models.CharField(max_length=6, null=True, verbose_name='邮编')
    rphone = models.CharField(max_length=11, verbose_name='联系电话')
    is_default = models.BooleanField(default=False, verbose_name='是否默认')

    objects = AddrManager()

    class Meta:
        db_table = 'df_address'
        verbose_name = '地址'
        verbose_name_plural = verbose_name
