from django.urls import path
from home.views import IndexView

urlpatterns = [
    #首页路由
    path('',IndexView.as_view(),name='index'),
]