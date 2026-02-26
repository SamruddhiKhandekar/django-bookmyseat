from django.urls import path
from . import views
urlpatterns=[
    path('',views.movie_list,name='movie_list'),
    path('<int:movie_id>/theaters',views.theater_list,name='theater_list'),
    path('theater/<int:theater_id>/seats/book/',views.book_seats,name='book_seats'),
    path('movie/<int:movie_id>/',views.movie_detail,name='movie_detail'),
    path('create-checkout-session/',views.create_checkout_session,name='create_checkout_session'),
    path('payment/',views.payment_page,name='payment_page'),
    path('payment-success/',views.payment_success,name='payment_success'),
    path('payment-failed/',views.payment_failed,name='payment_failed'),
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
]