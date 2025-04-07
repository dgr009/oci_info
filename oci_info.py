#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCI 정보 조회 스크립트 (인스턴스, LB, NSG)

[추가 사항]
1. 옵션 기반으로 원하는 정보만 출력
   - 인스턴스: --instance, -i
   - 로드 밸런서: --lb, -l
   - NSG: --nsg
   - 모두 출력(디폴트)
2. --name 옵션으로 필터링 (부분 일치)
   - --instance 또는 --lb 또는 --nsg 와 함께 사용 시 해당 리소스명만 필터
   - 여러 옵션(i, l, nsg)을 같이 쓰면, 각각에 대해 동일한 name 필터 적용
3. 예시:
   - python3 oci_info_extended.py # 모두 출력
   - python3 oci_info_extended.py --instance # 인스턴스만
   - python3 oci_info_extended.py --lb -nsg # LB, NSG만
   - python3 oci_info_extended.py -i --name my-instance # 인스턴스 중 이름에 'my-instance' 포함된 것만

"""

import oci
import argparse
from rich.console import Console
from rich.table import Table
from rich import box


def main():
    parser = argparse.ArgumentParser(description="OCI Info Extended")
    parser.add_argument("--instance", "-i", action="store_true", help="인스턴스 정보만 표시")
    parser.add_argument("--lb", "-l", action="store_true", help="로드 밸런서 정보만 표시")
    parser.add_argument("--nsg", "-s", action="store_true", help="NSG 인바운드 룰만 표시")
    parser.add_argument("--name", "-n", default=None, help="이름 필터 (부분 일치)")

    args = parser.parse_args()

    # 어느 것도 지정 안 했으면 모두 True
    show_instance = args.instance or args.lb or args.nsg == False
    if (not args.instance) and (not args.lb) and (not args.nsg):
        show_instance = True
        show_lb = True
        show_nsg = True
    else:
        show_instance = args.instance
        show_lb = args.lb
        show_nsg = args.nsg

    name_filter = args.name.lower() if args.name else None

    config = oci.config.from_file("~/.oci/config", "DEFAULT")

    identity_client = oci.identity.IdentityClient(config)
    compute_client = oci.core.ComputeClient(config)
    virtual_network_client = oci.core.VirtualNetworkClient(config)
    block_storage_client = oci.core.BlockstorageClient(config)
    loadbalancer_client = oci.load_balancer.LoadBalancerClient(config)

    tenancy_ocid = config["tenancy"]

    # 컴파트먼트 조회
    compartments = []
    resp = identity_client.list_compartments(
        tenancy_ocid,
        compartment_id_in_subtree=True,
        lifecycle_state="ACTIVE"
    )
    compartments.extend(resp.data)

    # 루트 compartment 추가
    root_comp = identity_client.get_compartment(tenancy_ocid).data
    compartments.append(root_comp)

    console = Console()

    # --------------------------------------------------------------------------------
    # 인스턴스 테이블
    # --------------------------------------------------------------------------------
    instance_table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
    instance_table.add_column("Compartment", style="bold magenta")
    instance_table.add_column("Instance Name", style="bold cyan")
    instance_table.add_column("State", justify="center")
    instance_table.add_column("Subnet")
    instance_table.add_column("NSG")
    instance_table.add_column("Private IP")
    instance_table.add_column("Public IP")
    instance_table.add_column("Shape")
    instance_table.add_column("vCPUs", justify="right")
    instance_table.add_column("Memory(GB)", justify="right")
    instance_table.add_column("Boot Volume", justify="left")
    instance_table.add_column("Block Volumes", justify="left")

    state_color_map = {
        "RUNNING": "green",
        "STOPPED": "yellow",
        "STOPPING": "yellow",
        "STARTING": "cyan",
        "PROVISIONING": "cyan",
        "TERMINATED": "red"
    }
    instance_rows = []

    if show_instance:
        for comp in compartments:
            comp_name = comp.name
            comp_id = comp.id

            try:
                instance_list = compute_client.list_instances(
                    compartment_id=comp_id
                ).data
            except Exception as e:
                console.print(f"[red][ERROR][/red] 컴파트먼트 {comp_name} 조회 실패: {e}")
                continue

            for instance in instance_list:
                if instance.lifecycle_state == "TERMINATED":
                    continue

                instance_name = instance.display_name
                # name_filter 적용(부분 일치)
                if name_filter and (name_filter not in instance_name.lower()):
                    continue

                instance_id = instance.id
                shape = instance.shape
                state = instance.lifecycle_state

                # vCPU / 메모리
                vcpus = "-"
                memory_in_gbs = "-"
                try:
                    inst_details = compute_client.get_instance(instance_id).data
                    if inst_details.shape_config and inst_details.shape_config.ocpus is not None:
                        ocpus = inst_details.shape_config.ocpus
                        vcpus = str(int(ocpus * 2))
                        memory_in_gbs = str(inst_details.shape_config.memory_in_gbs)
                except:
                    pass

                # VNIC
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
                        vnic_id = vnic_atts[0].vnic_id
                        vnic = virtual_network_client.get_vnic(vnic_id).data
                        private_ip_str = vnic.private_ip or "-"
                        public_ip_str = vnic.public_ip or "-"

                        # Subnet
                        try:
                            subnet_data = virtual_network_client.get_subnet(vnic.subnet_id).data
                            subnet_name_str = subnet_data.display_name
                        except:
                            pass

                        # NSG
                        if vnic.nsg_ids:
                            nsg_names = []
                            for nsg_id in vnic.nsg_ids:
                                try:
                                    nsg_obj = virtual_network_client.get_network_security_group(nsg_id).data
                                    nsg_names.append(nsg_obj.display_name)
                                except:
                                    nsg_names.append("Unknown-NSG")
                            nsg_name_str = ",".join(nsg_names)
                except Exception as e:
                    pass

                # Boot volume
                boot_volume_str = "-"
                try:
                    bv_atts = compute_client.list_boot_volume_attachments(
                        availability_domain=instance.availability_domain,
                        compartment_id=comp_id,
                        instance_id=instance_id
                    ).data
                    if bv_atts:
                        bv_id = bv_atts[0].boot_volume_id
                        bv = block_storage_client.get_boot_volume(bv_id).data
                        size_gb = bv.size_in_gbs
                        boot_volume_str = f"{size_gb}GB"
                except:
                    pass

                # Block volume
                block_volume_str = "-"
                try:
                    va_atts = compute_client.list_volume_attachments(
                        compartment_id=comp_id,
                        instance_id=instance_id
                    ).data
                    block_vols = []
                    for va in va_atts:
                        if not isinstance(va, oci.core.models.BootVolumeAttachment):
                            blk_id = va.volume_id
                            blk = block_storage_client.get_volume(blk_id).data
                            blk_size = blk.size_in_gbs
                            block_vols.append(f"{blk_size}GB")

                    if block_vols:
                        block_volume_str = ", ".join(block_vols)
                except:
                    pass

                state_color = state_color_map.get(state, "white")
                colored_state = f"[{state_color}]{state}[/{state_color}]"

                instance_rows.append({
                    "compartment_name": comp_name,
                    "instance_name": instance_name,
                    "state_colored": colored_state,
                    "subnet": subnet_name_str,
                    "nsg": nsg_name_str,
                    "private_ip": private_ip_str,
                    "public_ip": public_ip_str,
                    "shape": shape,
                    "vcpus": vcpus,
                    "memory": memory_in_gbs,
                    "boot_volume": boot_volume_str,
                    "block_volume": block_volume_str
                })

        # 정렬
        instance_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["instance_name"].lower()))

    # --------------------------------------------------------------------------------
    # LB 테이블
    # --------------------------------------------------------------------------------
    lb_table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
    lb_table.add_column("Compartment", style="bold magenta")
    lb_table.add_column("LB Name", style="bold cyan")
    lb_table.add_column("LB State", justify="center")
    lb_table.add_column("IP Addresses")
    lb_table.add_column("Shape")
    lb_table.add_column("Type")
    lb_table.add_column("Backend Set")
    lb_table.add_column("Backend Target")

    lb_rows = []
    lb_state_color_map = {
        "ACTIVE": "green",
        "PROVISIONING": "cyan",
        "FAILED": "red",
        "UPDATING": "yellow",
        "TERMINATED": "red"
    }

    if show_lb:
        for comp in compartments:
            comp_name = comp.name
            comp_id = comp.id

            try:
                lbs = loadbalancer_client.list_load_balancers(
                    compartment_id=comp_id
                ).data
            except Exception as e:
                continue

            for lb in lbs:
                lb_name = lb.display_name
                # name_filter 적용
                if name_filter and (name_filter not in lb_name.lower()):
                    continue

                lb_id = lb.id
                lb_state = lb.lifecycle_state
                shape_name = lb.shape_name if lb.shape_name else "-"

                # IP Addresses
                ip_str_list = []
                if lb.ip_addresses:
                    for ip_info in lb.ip_addresses:
                        ip_str_list.append(ip_info.ip_address or "-")
                ip_addrs_str = ", ".join(ip_str_list) if ip_str_list else "-"

                is_private = lb.is_private if hasattr(lb, 'is_private') else False
                lb_type_str = "PRIVATE" if is_private else "PUBLIC"

                # backend sets
                try:
                    backend_sets = loadbalancer_client.list_backend_sets(
                        load_balancer_id=lb_id
                    ).data
                except:
                    continue

                for backend_set_name in backend_sets.keys():
                    try:
                        backends = loadbalancer_client.list_backends(
                            load_balancer_id=lb_id,
                            backend_set_name=backend_set_name
                        ).data
                    except:
                        backends = []

                    if not backends:
                        lb_rows.append({
                            "compartment_name": comp_name,
                            "lb_name": lb_name,
                            "lb_state": lb_state,
                            "ip_addrs": ip_addrs_str,
                            "shape_name": shape_name,
                            "lb_type": lb_type_str,
                            "backend_set": backend_set_name,
                            "backend_target": "(No Backends)"
                        })
                    else:
                        for backend in backends:
                            backend_target = backend.target_id or backend.ip_address

                            lb_rows.append({
                                "compartment_name": comp_name,
                                "lb_name": lb_name,
                                "lb_state": lb_state,
                                "ip_addrs": ip_addrs_str,
                                "shape_name": shape_name,
                                "lb_type": lb_type_str,
                                "backend_set": backend_set_name,
                                "backend_target": backend_target
                            })

        lb_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["lb_name"].lower(), x["backend_set"].lower()))

    # --------------------------------------------------------------------------------
    # NSG 테이블
    # --------------------------------------------------------------------------------
    nsg_table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
    nsg_table.add_column("Compartment", style="bold magenta")
    nsg_table.add_column("NSG Name", style="bold cyan")
    nsg_table.add_column("Rule Desc", justify="left")
    nsg_table.add_column("Protocol", justify="left")
    nsg_table.add_column("Port Range", justify="left")
    nsg_table.add_column("Source")

    nsg_rows = []

    if show_nsg:
        for comp in compartments:
            comp_name = comp.name
            comp_id = comp.id

            try:
                nsg_list = virtual_network_client.list_network_security_groups(
                    compartment_id=comp_id
                ).data
            except:
                continue

            for nsg in nsg_list:
                nsg_name = nsg.display_name
                if name_filter and (name_filter not in nsg_name.lower()):
                    continue

                nsg_id = nsg.id

                # Ingress rule
                try:
                    rules_response = virtual_network_client.list_network_security_group_security_rules(
                        network_security_group_id=nsg_id
                    ).data
                    ingress_rules = [r for r in rules_response if r.direction == "INGRESS"]

                    for rule in ingress_rules:
                        desc = rule.description if rule.description else "-"
                        proto = rule.protocol

                        port_range_str = "-"
                        if rule.tcp_options and rule.tcp_options.destination_port_range:
                            pr = rule.tcp_options.destination_port_range
                            port_range_str = f"{pr.min}-{pr.max}"
                        elif rule.udp_options and rule.udp_options.destination_port_range:
                            pr = rule.udp_options.destination_port_range
                            port_range_str = f"{pr.min}-{pr.max}"

                        source_str = rule.source or "-"

                        protocol_str = proto
                        if proto == "6":
                            protocol_str = "TCP"
                        elif proto == "17":
                            protocol_str = "UDP"
                        elif proto == "1":
                            protocol_str = "ICMP"

                        nsg_rows.append({
                            "compartment_name": comp_name,
                            "nsg_name": nsg_name,
                            "desc": desc,
                            "proto": protocol_str,
                            "port_range": port_range_str,
                            "source": source_str
                        })
                except:
                    pass
        nsg_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["nsg_name"].lower()))

    # --------------------------------------------------------------------------------
    # 최종 출력
    # --------------------------------------------------------------------------------

    # 인스턴스 출력
    if show_instance:
        console.print("[bold underline]Instance Info[/bold underline]")
        if instance_rows:
            current_comp = None
            for row in instance_rows:
                if row["compartment_name"] != current_comp:
                    if current_comp is not None:
                        instance_table.add_section()
                    current_comp = row["compartment_name"]

                instance_table.add_row(
                    row["compartment_name"],
                    row["instance_name"],
                    row["state_colored"],
                    row["subnet"],
                    row["nsg"],
                    row["private_ip"],
                    row["public_ip"],
                    row["shape"],
                    row["vcpus"],
                    row["memory"],
                    row["boot_volume"],
                    row["block_volume"]
                )
            console.print(instance_table)
        else:
            console.print("(No Instances Matched)")

    # LB 출력
    if show_lb:
        console.print("\n[bold underline]Load Balancer Info[/bold underline]")
        if lb_rows:
            current_comp = None
            for row in lb_rows:
                if row["compartment_name"] != current_comp:
                    if current_comp is not None:
                        lb_table.add_section()
                    current_comp = row["compartment_name"]

                lb_state = row["lb_state"]
                color = lb_state_color_map.get(lb_state, "white")
                colored_lb_state = f"[{color}]{lb_state}[/{color}]"

                lb_table.add_row(
                    row["compartment_name"],
                    row["lb_name"],
                    colored_lb_state,
                    row["ip_addrs"],
                    row["shape_name"],
                    row["lb_type"],
                    row["backend_set"],
                    row["backend_target"]
                )
            console.print(lb_table)
        else:
            console.print("(No Load Balancers Matched)")

    # NSG 출력
    if show_nsg:
        console.print("\n[bold underline]NSG Inbound Rules[/bold underline]")
        if nsg_rows:
            current_comp = None
            for row in nsg_rows:
                if row["compartment_name"] != current_comp:
                    if current_comp is not None:
                        nsg_table.add_section()
                    current_comp = row["compartment_name"]

                nsg_table.add_row(
                    row["compartment_name"],
                    row["nsg_name"],
                    row["desc"],
                    row["proto"],
                    row["port_range"],
                    row["source"]
                )
            console.print(nsg_table)
        else:
            console.print("(No NSG Matched)")

if __name__ == "__main__":
    main()
