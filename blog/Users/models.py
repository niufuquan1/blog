from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    '''
    这样就满足了系统和本身自己的需求。
    '''
    mobile = models.CharField(max_length=11, unique=True, blank=False)

    avatar = models.ImageField(upload_to='avatar/%Y%m%d/', blank=True)

    user_desc = models.CharField(max_length=500, blank=True)

    #修改认证的字段为mobile
    USERNAME_FIELD = 'mobile'

    #创建超级管理员必须输入的字段（不包括手机号和密码）
    REQUIRED_FIELDS = ['username','email']

    class Meta:
        db_table = 'tb_users'  # 修改表名
        verbose_name = '用户管理'  # admin后台显示名称
        verbose_name_plural = verbose_name  # admin后台显示

    def __str__(self):
        return self.mobile
