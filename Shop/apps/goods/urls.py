from django.conf.urls import url
from .views import IndexView, DetailView, ListView


urlpatterns = [
    url(r'^index$', IndexView.as_view(), name='index'), # 首页
    url(r'^goods(?<goods_id>\d+)$', DetailView.as_view(), name='detail'), # 首页
    url(r'^list(?<type_id>\d+)$', DetailView.as_view(), name='list'), # 首页
]
