#from django.<a href="http" target="_blank">http</a> import HttpResponse
from django.http import HttpResponse
from django.urls import path

from . import views

from netbox_proxbox import proxbox_api
import json

urlpatterns = [
    # Home View
    path('', views.HomeView.as_view(), name='home'),
    path('lxc/', views.LxcListView.as_view(), name='lxc'),
    path('nodes/', views.NodesListView.as_view(), name='nodes'),
    path('resource-pool/', views.ResourcePoolListView.as_view(), name='resource_pool'),
    path('virtual-machine/', views.VirtualMachineListView.as_view(), name='virtual_machine'),
    path('virtual-machine/', views.StorageListView.as_view(), name='storage'),

    # Base Views
    path("list/", views.ProxmoxVMListView.as_view(), name="proxmoxvm_list"),
    # <int:pk> = plugins/netbox_proxmoxvm/<pk> | example: plugins/netbox_proxmoxvm/1/
    # ProxmoxVMView.as_view() - as.view() is need so that our view class can process requests.
    # as_view() takes request and returns well-formed response, that is a class based view.
    path("<int:pk>/", views.ProxmoxVMView.as_view(), name="proxmoxvm"),
    path("add/", views.ProxmoxVMCreateView.as_view(), name="proxmoxvm_add"),
    path("<int:pk>/delete/", views.ProxmoxVMDeleteView.as_view(), name="proxmoxvm_delete"),
    path("<int:pk>/edit/", views.ProxmoxVMEditView.as_view(), name="proxmoxvm_edit"),

    # Proxbox API full update
    #path("full_update/", ProxmoxVMFullUpdate.as_view(), name="proxmoxvm_full_update")
    path("full_update/", views.ProxmoxFullUpdate.as_view(), name="proxmoxvm_full_update")
]
