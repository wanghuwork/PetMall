from django.conf.urls import url
from .views import OrderPlaceView, OrderCommitView, OrderPayView, CheckPayView, CommentView
from . import views

urlpatterns = [
    url(r'^place$', OrderPlaceView.as_view(), name='place'),
    url(r'^commit$', OrderCommitView.as_view(), name='commit'),
    url(r'^pay$', OrderPayView.as_view(), name='pay'),
    url(r'^check$', CheckPayView.as_view(), name='check'),
    url(r'^comment(?<order_id>.+)$', CommentView.as_view(), name='comment')

]
