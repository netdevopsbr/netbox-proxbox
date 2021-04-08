from proxmoxer import ProxmoxAPI
import pynetbox

from __init__ import netbox as nb, proxmox

# Verifica se VM/CT existe no Proxmox
def is_vm_on_proxmox(netbox_vm):
    # Obtém o json de todas as máquinas virtuais do Proxmox
    all_proxmox_vms = proxmox.cluster.resources.get(type='vm')

    # Netbox name
    netbox_name = netbox_vm.name

    # Busca json local_context do Netbox
    local_context = netbox_vm.local_context_data

    if local_context == None:
        print('[WARNING] "local_context_data" não preenchido -> {}'.format(netbox_name))

    else:
        # chave "proxmox" do "local_context_data"
        proxmox_json = local_context.get("proxmox")
    
        # Se valor nulo, volta erro
        if proxmox_json == None:
            print('[WARNING] local_context_data não possui a chave "proxmox" -> {}'.format(netbox_name))   

        else:
            # Netbox VM/CT ID
            netbox_id = proxmox_json.get("id")

            # Se valor nulo, volta erro
            if netbox_id == None:
                print('[WARNING] chave "proxmox" não possui chave " -> {}'.format(netbox_name))


    # Lista de nomes das VM/CTs do Proxmox
    names = []

    # Lista de IDs das VM/CTs do Proxmox
    vmids = []

    # Compara VM do Netbox com todas as VMs do Proxmox e verifica se existe no Proxmox
    for i in range(len(all_proxmox_vms)):
        name = all_proxmox_vms[i].get("name")
        names.append(name)

        vm_id = all_proxmox_vms[i].get("vmid")
        vmids.append(vm_id)
    

    name_on_px = False
    id_on_px = False

    # Busca VM no Proxmox pelo nome
    try:
        name_index = names.index(netbox_name)      
    except:
        name_on_px = False
    else:
        # ID existe no Proxmox
        name_on_px = True
        
        # Se local_context é nulo, tenta preenchê-lo para obter ID da VM
        if local_context == None:
            local_context_updated = local_context_data(netbox_vm, all_proxmox_vms[name_index])

            if local_context_updated == True:
                local_context = netbox_vm.local_context_data

                if local_context != None:
                    print("[OK] local_context atualizado -> {}".format(netbox_name))
                    proxmox_json = local_context.get("proxmox")
                    netbox_id = proxmox_json.get("id")

                else:
                    print("[ERROR] local_context está vazio -> {}".format(netbox_name))
            else:
                print("[WARNING] local_context não foi atualizado (erro ou já estava atualizado) -> {}".format(netbox_name))


    # Busca VM no Proxmox pelo ID
    try:
        id_index = vmids.index(netbox_id)
    except:
        id_on_px = False
    else:
        # NAME existe no Proxmox
        id_on_px = True

    # Analisa se VM existe
    if name_on_px == True:
        if id_on_px == True:
            return True
        else:
            print("[WARNING] NOME existe no Proxmox, mas ID não -> {}".format(netbox_name))
        return True
    
    # Comparação não deu certo, não possíve achar VM no Proxmox
    return False

def virtual_machine():
    # Get all VM/CTs from Netbox
    netbox_all_vms = nb.virtualization.virtual_machines.all()

    for nb_vm_each in netbox_all_vms:
        netbox_obj = nb_vm_each
        netbox_name = netbox_obj.name

        # Verifica se VM existe ou não no Proxmox
        vm_on_proxmox = is_vm_on_proxmox(nb_vm_each)

        if vm_on_proxmox == True:
            print('[OK] VM existe em ambos sistemas -> {}'.format(netbox_name))
        
        # Se VM não existe no Proxmox, deleta a VM no Netbox
        elif vm_on_proxmox == False:
            print("[WARNING] VM existe no Netbox, mas não no Proxmox. Deletar a VM! -> {}".format(netbox_name))
            delete_vm = netbox_obj.delete()

            if delete_vm == True:
                print("[OK] VM removida do Netbox com sucesso")

        else:
            print('[ERROR] Erro inesperado ao verificar se VM existe no Proxmox')