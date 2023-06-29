from extras.plugins import PluginMenuButton, PluginMenuItem
from utilities.choices import ButtonColorChoices

menu_items = (
    PluginMenuItem(
        link="plugins:netbox_proxbox:home",
        link_text="Home",
    ),
    PluginMenuItem(
        link="plugins:netbox_proxbox:nodes",
        link_text="Nodes",
    ),
    PluginMenuItem(
        link="plugins:netbox_proxbox:lxc",
        link_text="LXC Container",
    ),
    PluginMenuItem(
        link="plugins:netbox_proxbox:virtual_machine",
        link_text="Virtual Machine",
    ),
    PluginMenuItem(
        link="plugins:netbox_proxbox:storage",
        link_text="Storage",
    ),
)

'''
buttons=(
    PluginMenuButton(
        # match the names of the path for create view defined in ./urls.py
        link="plugins:netbox_proxbox:proxmoxvm_add",
        # text that appears when hovering the ubtton
        title="Add",
        # font-awesome icon to use
        icon_class="mdi mdi-plus-thick", # 'fa fa-plus' didn't work
        # defines color button to green
        color=ButtonColorChoices.GREEN,
        permissions=["netbox_proxbox.add_proxmoxvm"],
    ),
),
'''