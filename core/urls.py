from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/v1/auth/', include('apps.accounts.urls')), 
    path('api/v1/', include('apps.observations.urls')),
    path('api/v1/community/', include('apps.community.urls')),
    # path('api/v1/payments/', include('apps.payments.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)