#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import oci
from rich.console import Console
from rich.table import Table

def main():
    config = oci.config.from_file("~/.oci/config", "DEFAULT")
    
    identity_client = oci.identity.IdentityClient(config)
    compute_client = oci.core.ComputeClient(config)
    virtual_network_client = oci.core.VirtualNetworkClient(config)
    block_storage_client = oci.core.BlockstorageClient(config)
    
    tenancy_ocid = config["tenancy"]
    
    # 컴파트먼트 목록 (하위 포함, ACTIVE)
    compartments = []
    resp = identity_client.list_compartments(
        tenancy_ocid,
        compartment_id_in_subtree=True,
        lifecycle_state="ACTIVE"
    )
    compartments.extend(resp.data)
    
    # 루트 Compartment(테넌시) 자체도 추가
    root_comp = identity_client.get_compartment(tenancy_ocid).data
    compartments.append(root_comp)
    
    # 테이블 구조
    console = Console()
    table = Table(show_lines=False)
    table.add_column("Compartment", style="bold magenta")
    table.add_column("Instance Name", style="bold cyan")
    table.add_column("Subnet")
    table.add_column("NSG")
    table.add_column("Private IP")
    table.add_column("Public IP")
    table.add_column("Shape")
    table.add_column("vCPUs", justify="right")
    table.add_column("Memory(GB)", justify="right")
    table.add_column("Boot Volume", justify="left")
    table.add_column("Block Volumes", justify="left")
    
    instance_rows = []
    
    for comp in compartments:
        comp_id = comp.id
        comp_name = comp.name
        
        try:
            instances = compute_client.list_instances(compartment_id=comp_id).data
        except Exception as e:
            console.print(f"[red][ERROR][/red] 컴파트먼트 {comp_name} 조회 실패: {e}")
            continue
        
        for instance in instances:
            if instance.lifecycle_state == "TERMINATED":
                continue  # 종료된 인스턴스 제외
            
            instance_name = instance.display_name
            instance_id = instance.id
            
            # vCPU / 메모리
            shape = instance.shape
            vcpus = "-"
            memory_in_gbs = "-"
            try:
                inst_details = compute_client.get_instance(instance_id).data
                if inst_details.shape_config and inst_details.shape_config.ocpus is not None:
                    # OCI에서 1 OCPU = 2 vCPU로 가정
                    ocpus = inst_details.shape_config.ocpus
                    vcpus = str(int(ocpus * 2))
                    memory_in_gbs = str(inst_details.shape_config.memory_in_gbs)
            except Exception as e:
                console.print(f"[yellow]인스턴스 {instance_name} shape_config 조회 실패: {e}[/yellow]")
            
            # VNIC: private/public IP, subnet, NSG
            private_ip_str = "-"
            public_ip_str = "-"
            subnet_name_str = "-"
            nsg_name_str = "-"
            try:
                vnic_atts = compute_client.list_vnic_attachments(
                    compartment_id=comp_id,
                    instance_id=instance_id
                ).data
                if vnic_atts:
                    # 첫 번째 VNIC만 표시
                    vnic_id = vnic_atts[0].vnic_id
                    vnic = virtual_network_client.get_vnic(vnic_id).data
                    
                    private_ip_str = vnic.private_ip or "-"
                    public_ip_str = vnic.public_ip or "-"
                    
                    # 서브넷명
                    try:
                        subnet = virtual_network_client.get_subnet(vnic.subnet_id).data
                        subnet_name_str = subnet.display_name
                    except:
                        subnet_name_str = "Unknown-Subnet"
                    
                    # NSG
                    if vnic.nsg_ids:
                        nsg_list = []
                        for nsg_id in vnic.nsg_ids:
                            try:
                                nsg_obj = virtual_network_client.get_network_security_group(nsg_id).data
                                nsg_list.append(nsg_obj.display_name)
                            except:
                                nsg_list.append("Unknown-NSG")
                        nsg_name_str = ",".join(nsg_list)
            except Exception as e:
                console.print(f"[yellow]인스턴스 {instance_name} VNIC 조회 실패: {e}[/yellow]")
            
            # Boot Volume (list_boot_volume_attachments 사용)
            boot_volume_str = "-"
            try:
                bv_atts = compute_client.list_boot_volume_attachments(
                    availability_domain=instance.availability_domain,
                    compartment_id=comp_id,
                    instance_id=instance_id
                ).data
                if bv_atts:
                    # 일반적으로 인스턴스에는 1개의 BootVolumeAttachment만 존재
                    bv_id = bv_atts[0].boot_volume_id
                    try:
                        bv = block_storage_client.get_boot_volume(bv_id).data
                        size_gb = bv.size_in_gbs
                        name = bv.display_name
                        boot_volume_str = f"{size_gb}GB"
                    except:
                        boot_volume_str = f"Unknown)"
            except Exception as e:
                console.print(f"[yellow]인스턴스 {instance_name} BootVolume 조회 실패: {e}[/yellow]")
            
            # Block Volumes (list_volume_attachments 사용)
            block_volume_str = "-"
            try:
                va_atts = compute_client.list_volume_attachments(
                    compartment_id=comp_id,
                    instance_id=instance_id
                ).data
                
                block_volumes = []
                for va in va_atts:
                    # BootVolumeAttachment가 아닌 애들 => block volume
                    if not isinstance(va, oci.core.models.BootVolumeAttachment):
                        blk_id = va.volume_id
                        try:
                            blk = block_storage_client.get_volume(blk_id).data
                            blk_size = blk.size_in_gbs
                            blk_name = blk.display_name
                            block_volumes.append(f"{blk_size}GB")
                        except:
                            block_volumes.append(f"Unknow")
                
                if block_volumes:
                    block_volume_str = ", ".join(block_volumes)
            except Exception as e:
                console.print(f"[yellow]인스턴스 {instance_name} BlockVolume 조회 실패: {e}[/yellow]")
            
            instance_rows.append({
                "compartment_name": comp_name,
                "instance_name": instance_name,
                "subnet_name": subnet_name_str,
                "nsg_name": nsg_name_str,
                "private_ip": private_ip_str,
                "public_ip": public_ip_str,
                "shape": shape,
                "vcpus": vcpus,
                "memory": memory_in_gbs,
                "boot_vol": boot_volume_str,
                "block_vol": block_volume_str
            })
    
    # 정렬
    instance_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["instance_name"].lower()))
    
    # 테이블에 데이터 채우기
    current_comp = None
    for row in instance_rows:
        if row["compartment_name"] != current_comp:
            if current_comp is not None:
                table.add_section()
            current_comp = row["compartment_name"]
        
        table.add_row(
            row["compartment_name"],
            row["instance_name"],
            row["subnet_name"],
            row["nsg_name"],
            row["private_ip"],
            row["public_ip"],
            row["shape"],
            row["vcpus"],
            row["memory"],
            row["boot_vol"],
            row["block_vol"]
        )
    
    console.print(table)

if __name__ == "__main__":
    main()
