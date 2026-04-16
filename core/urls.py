from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('market/', views.market, name='market'),
    path('wallet/', views.wallet_view, name='wallet'),
    path('order-history/', views.order_history_view, name='order_history'),
    path('transaction-history/', views.transaction_history_view, name='transaction_history'),
    path('profile/', views.profile_view, name='profile'),
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.logout_view, name='logout'),
    path('suspended/', views.suspended_page, name='suspended_page'),
    path('deposit/', views.wallet_view, name='deposit'),
    path('order/cancel/<int:order_id>/', views.cancel_order, name='cancel_order'),
    path('api/assets/', views.api_assets, name='api_assets'),
    path('api/toggle-demo/', views.toggle_demo_mode, name='toggle_demo_mode'),
    path('api/profile/upload-avatar/', views.api_upload_avatar, name='api_upload_avatar'),
    path('broker-chat/', views.user_chat_view, name='user_chat'),
    
    # Minor Pages
    path('terms/', views.terms_view, name='terms'),
    path('privacy/', views.privacy_view, name='privacy'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    
    # Custom Admin Console
    path('et-admin/', views.custom_admin_dashboard, name='custom_admin_dashboard'),
    path('et-admin/users/', views.custom_admin_users, name='custom_admin_users'),
    path('et-admin/assets/', views.custom_admin_assets, name='custom_admin_assets'),
    path('et-admin/orders/', views.custom_admin_orders, name='custom_admin_orders'),
    path('et-admin/deposits/', views.admin_deposits, name='admin_deposits'),
    path('et-admin/withdrawals/', views.admin_withdrawals, name='admin_withdrawals'),
    path('et-admin/investments/', views.custom_admin_investments, name='custom_admin_investments'),
    path('et-admin/ai-trading/', views.admin_ai_trading, name='admin_ai_trading'),
    path('et-admin/security-logs/', views.admin_security_logs, name='admin_security_logs'),
    path('et-admin/managed-history/', views.admin_managed_history, name='admin_managed_history'),
    path('et-admin/chat/<int:user_id>/signal/', views.admin_send_signal, name='admin_send_signal'),
    path('et-admin/user/<int:user_id>/detail/', views.custom_admin_user_detail, name='custom_admin_user_detail'),
    path('et-admin/manage-addresses/', views.admin_manage_addresses, name='admin_manage_addresses'),
    
    # Custom Admin Actions
    path('et-admin/tx/<int:tx_id>/approve/', views.admin_approve_tx, name='admin_approve_tx'),
    path('et-admin/tx/<int:tx_id>/reject/', views.admin_reject_tx, name='admin_reject_tx'),
    path('et-admin/investment/<int:payment_id>/approve/', views.admin_approve_investment, name='admin_approve_investment'),
    path('et-admin/investment/<int:payment_id>/reject/', views.admin_reject_investment, name='admin_reject_investment'),
    path('et-admin/user/<int:user_id>/verify/', views.admin_verify_user, name='admin_verify_user'),
    path('et-admin/user/<int:user_id>/reject-kyc/', views.admin_reject_kyc, name='admin_reject_kyc'),
    
    # Broker Chat URLs
    path('api/chat/get/', views.api_get_messages, name='api_get_messages'),
    path('api/chat/send/', views.api_send_message, name='api_send_message'),
    path('api/chat/mark-read/', views.api_mark_as_read, name='api_mark_as_read'),
    path('api/admin/chat/list/', views.api_admin_chat_list, name='api_admin_chat_list'),
    path('api/admin/chat/get/<int:user_id>/', views.api_admin_get_messages, name='api_admin_get_messages'),
    path('api/admin/chat/send/<int:user_id>/', views.api_admin_send_message, name='api_admin_send_message'),
    path('api/admin/chat/delete/<int:message_id>/', views.api_admin_delete_message, name='api_admin_delete_message'),
    path('et-admin/chats/', views.admin_chat_list, name='admin_chat_list'),
    path('et-admin/chat/<int:user_id>/', views.admin_chat_detail, name='admin_chat_detail'),

    # Expert Signals & Investment URLs
    path('api/signals/respond/', views.api_respond_signal, name='api_respond_signal'),
    path('investment-plans/', views.investment_plans_view, name='investment_plans'),
    path('investment-tiers/', views.investment_tiers_view, name='investment_tiers'),
    path('investment-checkout/', views.investment_checkout_view, name='investment_checkout'),
    path('my-investments/', views.my_investments_view, name='my_investments'),
    path('managed-trading/', views.user_ai_trades_view, name='user_ai_trades'),
    path('et-admin/manage-trade/<int:trade_id>/<str:action>/', views.admin_manage_trade_action, name='admin_manage_trade_action'),
    path('et-admin/send-signal/<int:user_id>/', views.admin_send_signal, name='admin_send_signal'),
    path('et-admin/toggle-service/<int:user_id>/<str:service_type>/', views.admin_toggle_service, name='admin_toggle_service'),
]
