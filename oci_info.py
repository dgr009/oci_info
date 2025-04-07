#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
OCI 정보 조회 스크립트 (인스턴스, LB, NSG, 볼륨, 오브젝트 스토리지)

[기능 요약]
- 인스턴스 정보 (--instance / -i)
- 로드 밸런서 (--lb / -l)
- NSG 인바운드 룰 (--nsg / -s)
- 볼륨(부팅 볼륨 / 블록 볼륨) (--volume / -v)
- 오브젝트 스토리지(버킷) (--object / -o)

[옵션 설명]
1) 어느 것도 지정하지 않으면, 모든 리소스를 조회합니다.
2) --name (-n) 으로 리소스 이름 필터(부분 일치)
3) --compartment (-c) 으로 컴파트먼트 이름 필터(부분 일치)
4) 인스턴스, LB, NSG, 볼륨, 버킷 모두 compartment별로 구분선이 들어가며, 각 리소스별로 별도 테이블로 표시

예시:
   - python3 oci_info_extended.py                  # 모두 출력
   - python3 oci_info_extended.py --instance       # 인스턴스만
   - python3 oci_info_extended.py --lb -nsg        # LB, NSG만
   - python3 oci_info_extended.py --volume         # 볼륨 정보만
   - python3 oci_info_extended.py --object         # 오브젝트 스토리지(버킷)만
   - python3 oci_info_extended.py -v -o            # 볼륨 + 오브젝트 스토리지
   - python3 oci_info_extended.py -i --name myinst # 인스턴스 중 이름에 'myinst' 포함만
   - python3 oci_info_extended.py -c dev           # 'dev'가 포함된 컴파트먼트에서만 조회
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
    parser.add_argument("--volume", "-v", action="store_true", help="볼륨 정보만 표시 (부팅/블록)")
    parser.add_argument("--object", "-o", action="store_true", help="오브젝트 스토리지(버킷) 정보만 표시")
    parser.add_argument("--name", "-n", default=None, help="이름 필터 (부분 일치)")
    parser.add_argument("--compartment", "-c", default=None, help="컴파트먼트 이름 필터 (부분 일치)")

    args = parser.parse_args()

    # 어느 것도 지정 안 했다면 => 모두 True
    # (기존: 인스턴스, LB, NSG에만 적용했으나, 볼륨, 오브젝트 스토리지도 추가)
    if not (args.instance or args.lb or args.nsg or args.volume or args.object):
        show_instance = True
        show_lb = True
        show_nsg = True
        show_volume = True
        show_object = True
    else:
        show_instance = args.instance
        show_lb = args.lb
        show_nsg = args.nsg
        show_volume = args.volume
        show_object = args.object

    name_filter = args.name.lower() if args.name else None
    compartment_filter = args.compartment.lower() if args.compartment else None

    # -------------------------------------------------------------------------
    # OCI 클라이언트 생성
    # -------------------------------------------------------------------------
    config = oci.config.from_file("~/.oci/config", "DEFAULT")
    identity_client = oci.identity.IdentityClient(config)
    compute_client = oci.core.ComputeClient(config)
    virtual_network_client = oci.core.VirtualNetworkClient(config)
    block_storage_client = oci.core.BlockstorageClient(config)
    loadbalancer_client = oci.load_balancer.LoadBalancerClient(config)
    object_storage_client = oci.object_storage.ObjectStorageClient(config)

    tenancy_ocid = config["tenancy"]

    console = Console()

    # -------------------------------------------------------------------------
    # 컴파트먼트 목록 가져오기
    # -------------------------------------------------------------------------
    compartments = []
    try:
        resp = identity_client.list_compartments(
            tenancy_ocid,
            compartment_id_in_subtree=True,
            lifecycle_state="ACTIVE"
        )
        compartments.extend(resp.data)
        # tenancy도 하나의 compartment처럼 추가
        root_comp = identity_client.get_compartment(tenancy_ocid).data
        compartments.append(root_comp)
    except Exception as e:
        console.print(f"[red]컴파트먼트 목록 조회 실패: {e}[/red]")
        return

    # 컴파트먼트 이름 필터 적용
    if compartment_filter:
        compartments = [
            c for c in compartments
            if compartment_filter in c.name.lower()
        ]
        if not compartments:
            console.print(f"[yellow]컴파트먼트 '{args.compartment}'(으)로 필터링된 결과가 없습니다.[/yellow]")

    # -------------------------------------------------------------------------
    # [1] 인스턴스 정보
    # -------------------------------------------------------------------------
    instance_rows = []
    state_color_map = {
        "RUNNING": "green",
        "STOPPED": "yellow",
        "STOPPING": "yellow",
        "STARTING": "cyan",
        "PROVISIONING": "cyan",
        "TERMINATED": "red",
        "AVAILABLE": "green"
    }

    if show_instance:
        for comp in compartments:
            comp_id = comp.id
            comp_name = comp.name

            try:
                inst_list = compute_client.list_instances(compartment_id=comp_id).data
            except Exception as e:
                console.print(f"[red][ERROR][/red] 인스턴스 조회 실패 {comp_name}: {e}")
                continue

            for inst in inst_list:
                if inst.lifecycle_state == "TERMINATED":
                    continue

                # 이름 필터
                if name_filter and (name_filter not in inst.display_name.lower()):
                    continue

                instance_id = inst.id
                shape = inst.shape
                state = inst.lifecycle_state

                # vCPU / Memory
                vcpus = "-"
                memory_gbs = "-"
                try:
                    details = compute_client.get_instance(instance_id).data
                    if details.shape_config and details.shape_config.ocpus is not None:
                        ocpus = details.shape_config.ocpus
                        vcpus = str(int(ocpus * 2))
                        memory_gbs = str(details.shape_config.memory_in_gbs)
                except:
                    pass

                # VNIC (첫번째 VNIC만)
                private_ip = "-"
                public_ip = "-"
                subnet_str = "-"
                nsg_str = "-"
                try:
                    vnic_atts = compute_client.list_vnic_attachments(
                        compartment_id=comp_id,
                        instance_id=instance_id
                    ).data
                    if vnic_atts:
                        vnic_id = vnic_atts[0].vnic_id
                        vnic = virtual_network_client.get_vnic(vnic_id).data
                        private_ip = vnic.private_ip or "-"
                        public_ip = vnic.public_ip or "-"

                        # Subnet
                        try:
                            subnet_info = virtual_network_client.get_subnet(vnic.subnet_id).data
                            subnet_str = subnet_info.display_name
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
                            nsg_str = ",".join(nsg_names)
                except:
                    pass

                # Boot Volume
                boot_str = "-"
                try:
                    bvas = compute_client.list_boot_volume_attachments(
                        availability_domain=inst.availability_domain,
                        compartment_id=comp_id,
                        instance_id=instance_id
                    ).data
                    if bvas:
                        bv_id = bvas[0].boot_volume_id
                        bv = block_storage_client.get_boot_volume(bv_id).data
                        boot_str = f"{bv.size_in_gbs}GB"
                except:
                    pass

                # Block Volume
                block_str = "-"
                try:
                    vas = compute_client.list_volume_attachments(
                        compartment_id=comp_id,
                        instance_id=instance_id
                    ).data
                    block_list = []
                    for va in vas:
                        if not isinstance(va, oci.core.models.BootVolumeAttachment):
                            vol_id = va.volume_id
                            vol_data = block_storage_client.get_volume(vol_id).data
                            block_list.append(f"{vol_data.size_in_gbs}GB")
                    if block_list:
                        block_str = ", ".join(block_list)
                except:
                    pass

                color = state_color_map.get(state, "white")
                state_colored = f"[{color}]{state}[/{color}]"

                instance_rows.append({
                    "compartment_name": comp_name,
                    "instance_name": inst.display_name,
                    "state_colored": state_colored,
                    "subnet": subnet_str,
                    "nsg": nsg_str,
                    "private_ip": private_ip,
                    "public_ip": public_ip,
                    "shape": shape,
                    "vcpus": vcpus,
                    "memory": memory_gbs,
                    "boot": boot_str,
                    "block": block_str
                })

        instance_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["instance_name"].lower()))

    # -------------------------------------------------------------------------
    # [2] 로드 밸런서 정보
    # -------------------------------------------------------------------------
    lb_rows = []
    lb_state_map = {
        "ACTIVE": "green",
        "PROVISIONING": "cyan",
        "FAILED": "red",
        "UPDATING": "yellow",
        "TERMINATED": "red"
    }

    if show_lb:
        for comp in compartments:
            comp_id = comp.id
            comp_name = comp.name

            try:
                lb_list = loadbalancer_client.list_load_balancers(compartment_id=comp_id).data
            except:
                continue

            for lb in lb_list:
                # 이름 필터
                if name_filter and (name_filter not in lb.display_name.lower()):
                    continue

                lb_state = lb.lifecycle_state
                shape_name = lb.shape_name if lb.shape_name else "-"
                ip_list = []
                if lb.ip_addresses:
                    ip_list = [ip.ip_address or "-" for ip in lb.ip_addresses]
                ip_addr_str = ", ".join(ip_list) if ip_list else "-"
                lb_type = "PRIVATE" if (getattr(lb, 'is_private', False)) else "PUBLIC"

                # backend sets
                try:
                    bsets = loadbalancer_client.list_backend_sets(load_balancer_id=lb.id).data
                except:
                    bsets = {}

                if not bsets:
                    lb_rows.append({
                        "compartment_name": comp_name,
                        "lb_name": lb.display_name,
                        "lb_state": lb_state,
                        "ip_addrs": ip_addr_str,
                        "shape": shape_name,
                        "lb_type": lb_type,
                        "backend_set": "(No Backend Sets)",
                        "backend_target": "-"
                    })
                else:
                    for backend_set_name in bsets.keys():
                        # list backends
                        try:
                            backend_list = loadbalancer_client.list_backends(
                                load_balancer_id=lb.id,
                                backend_set_name=backend_set_name
                            ).data
                        except:
                            backend_list = []

                        if not backend_list:
                            lb_rows.append({
                                "compartment_name": comp_name,
                                "lb_name": lb.display_name,
                                "lb_state": lb_state,
                                "ip_addrs": ip_addr_str,
                                "shape": shape_name,
                                "lb_type": lb_type,
                                "backend_set": backend_set_name,
                                "backend_target": "(No Backends)"
                            })
                        else:
                            for backend in backend_list:
                                tgt = backend.target_id or backend.ip_address
                                lb_rows.append({
                                    "compartment_name": comp_name,
                                    "lb_name": lb.display_name,
                                    "lb_state": lb_state,
                                    "ip_addrs": ip_addr_str,
                                    "shape": shape_name,
                                    "lb_type": lb_type,
                                    "backend_set": backend_set_name,
                                    "backend_target": tgt
                                })

        lb_rows.sort(key=lambda x: (
            x["compartment_name"].lower(),
            x["lb_name"].lower(),
            x["backend_set"].lower()
        ))

    # -------------------------------------------------------------------------
    # [3] NSG 정보 (Inbound 룰)
    # -------------------------------------------------------------------------
    nsg_rows = []
    if show_nsg:
        for comp in compartments:
            comp_name = comp.name
            comp_id = comp.id

            try:
                nsg_list = virtual_network_client.list_network_security_groups(compartment_id=comp_id).data
            except:
                continue

            for nsg in nsg_list:
                # 이름 필터
                if name_filter and (name_filter not in nsg.display_name.lower()):
                    continue

                try:
                    rules_res = virtual_network_client.list_network_security_group_security_rules(
                        network_security_group_id=nsg.id
                    ).data
                    ingress_rules = [r for r in rules_res if r.direction == "INGRESS"]
                except:
                    ingress_rules = []

                if not ingress_rules:
                    nsg_rows.append({
                        "compartment_name": comp_name,
                        "nsg_name": nsg.display_name,
                        "desc": "(No Ingress Rules)",
                        "proto": "-",
                        "port_range": "-",
                        "source": "-"
                    })
                else:
                    for rule in ingress_rules:
                        desc = rule.description if rule.description else "-"
                        proto = rule.protocol
                        port_range = "-"
                        if rule.tcp_options and rule.tcp_options.destination_port_range:
                            rng = rule.tcp_options.destination_port_range
                            port_range = f"{rng.min}-{rng.max}"
                        elif rule.udp_options and rule.udp_options.destination_port_range:
                            rng = rule.udp_options.destination_port_range
                            port_range = f"{rng.min}-{rng.max}"

                        source_str = rule.source or "-"
                        if proto == "6":
                            proto_str = "TCP"
                        elif proto == "17":
                            proto_str = "UDP"
                        elif proto == "1":
                            proto_str = "ICMP"
                        else:
                            proto_str = proto

                        nsg_rows.append({
                            "compartment_name": comp_name,
                            "nsg_name": nsg.display_name,
                            "desc": desc,
                            "proto": proto_str,
                            "port_range": port_range,
                            "source": source_str
                        })

        nsg_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["nsg_name"].lower()))

    # -------------------------------------------------------------------------
    # [4] 볼륨 정보 (부팅 볼륨, 블록 볼륨)
    # -------------------------------------------------------------------------
    # 1) 부팅 볼륨
    boot_rows = []
    # 2) 블록 볼륨
    block_rows = []

    if show_volume:
        # Availability Domain 목록 (부팅 볼륨은 AD 단위로 조회)
        try:
            ad_list = identity_client.list_availability_domains(tenancy_ocid).data
        except Exception as e:
            console.print(f"[red]AD 조회 실패: {e}[/red]")
            ad_list = []

        # 부팅 볼륨
        for comp in compartments:
            comp_name = comp.name
            comp_id = comp.id

            # 모든 AD에 대해 list_boot_volumes
            for ad in ad_list:
                ad_name = ad.name
                try:
                    b_vols = block_storage_client.list_boot_volumes(
                        availability_domain=ad_name,
                        compartment_id=comp_id
                    ).data
                except:
                    b_vols = []

                for bv in b_vols:
                    # 이름 필터
                    if name_filter and (name_filter not in bv.display_name.lower()):
                        continue

                    # 볼륨 상태, 사이즈, 붙어있는 인스턴스(있는 경우)
                    state = bv.lifecycle_state
                    size_gb = bv.size_in_gbs
                    vol_name = bv.display_name

                    rv_color = state_color_map.get(state, "white")
                    state_rv_colored = f"[{rv_color}]{state}[/{rv_color}]"

                    # Attachment 여부 확인
                    # list_boot_volume_attachments 에 volume_id는 없음 -> 사용 불가
                    # → 아래처럼 list_boot_volume_attachments로 전체를 불러와서 matching
                    attached_instance_name = "-"
                    try:
                        bvas = compute_client.list_boot_volume_attachments(
                            availability_domain=ad_name,
                            compartment_id=comp_id
                        ).data
                        for bva in bvas:
                            if bva.boot_volume_id == bv.id:
                                # 인스턴스 이름 찾아보기
                                try:
                                    inst_data = compute_client.get_instance(bva.instance_id).data
                                    attached_instance_name = inst_data.display_name
                                except:
                                    attached_instance_name = bva.instance_id
                                break
                    except:
                        pass

                    boot_rows.append({
                        "compartment_name": comp_name,
                        "volume_name": vol_name,
                        "state": state_rv_colored,
                        "size_gb": size_gb,
                        "attached": attached_instance_name
                    })

        # 블록 볼륨
        for comp in compartments:
            comp_name = comp.name
            comp_id = comp.id
            try:
                volumes = block_storage_client.list_volumes(compartment_id=comp_id).data
            except:
                volumes = []

            for vol in volumes:
                if name_filter and (name_filter not in vol.display_name.lower()):
                    continue

                vol_name = vol.display_name
                vol_state = vol.lifecycle_state
                size_gb = vol.size_in_gbs
                vol_id = vol.id

                bv_color = state_color_map.get(vol_state, "white")
                state_bv_colored = f"[{bv_color}]{vol_state}[/{bv_color}]"

                # 붙어있는 인스턴스 찾기
                attached_inst_name = "-"
                try:
                    # list_volume_attachments에 volume_id 필터 사용
                    attachments = compute_client.list_volume_attachments(
                        compartment_id=comp_id,
                        volume_id=vol_id
                    ).data
                    if attachments:
                        # 여러개가 붙을 수 있지만 일반적으로 1개
                        att = attachments[0]
                        try:
                            inst_obj = compute_client.get_instance(att.instance_id).data
                            attached_inst_name = inst_obj.display_name
                        except:
                            attached_inst_name = att.instance_id
                except:
                    pass

                block_rows.append({
                    "compartment_name": comp_name,
                    "volume_name": vol_name,
                    "state": state_bv_colored,
                    "size_gb": size_gb,
                    "attached": attached_inst_name
                })

        # 정렬
        boot_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["volume_name"].lower()))
        block_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["volume_name"].lower()))

    # -------------------------------------------------------------------------
    # [5] 오브젝트 스토리지 (버킷)
    # -------------------------------------------------------------------------
    object_rows = []
    if show_object:
        # Object Storage namespace
        try:
            namespace = object_storage_client.get_namespace().data
        except Exception as e:
            console.print(f"[red]Object Storage Namespace 조회 실패: {e}[/red]")
            namespace = None

        if namespace:
            for comp in compartments:
                comp_name = comp.name
                comp_id = comp.id
                try:
                    buckets = object_storage_client.list_buckets(
                        namespace_name=namespace,
                        compartment_id=comp_id
                    ).data
                except:
                    buckets = []

                for bkt in buckets:
                    # --name 필터
                    if name_filter and (name_filter not in bkt.name.lower()):
                        continue

                    # 버킷 get: public_access_type, storage_tier
                    # 하지만 approximate_size/approximate_count는 null일 수 있음
                    access_str = "NoPublicAccess"
                    tier_str = "-"
                    try:
                        bkt_detail = object_storage_client.get_bucket(
                            namespace_name=namespace,
                            bucket_name=bkt.name
                        ).data
                        if bkt_detail.public_access_type:
                            access_str = bkt_detail.public_access_type
                        if bkt_detail.storage_tier:
                            tier_str = bkt_detail.storage_tier
                    except:
                        pass

                    # public_access_type에 색상 추가 (노랑 / 초록)
                    access_color_map = {
                        "NoPublicAccess": "yellow",  # 노랑
                        # 그외(예: ObjectRead, ObjectReadWrite 등) → 초록
                    }
                    color = access_color_map.get(access_str, "green")
                    colored_access_str = f"[{color}]{access_str}[/{color}]"

                    # 버킷 내 실제 오브젝트 합산
                    total_size_bytes = 0
                    total_count = 0

                    # list_objects() → while loop로 페이지네이션
                    next_start = None
                    while True:
                        try:
                            list_resp = object_storage_client.list_objects(
                                namespace_name=namespace,
                                bucket_name=bkt.name,
                                start=next_start,
                                limit=1000,  # 한 페이지 최대 건수
                                fields="size,etag"
                            )
                        except:
                            break

                        objs = list_resp.data.objects or []
                        total_count += len(objs)

                        for obj in objs:
                            total_size_bytes += obj.size or 0

                        # 다음 페이지가 있는지 확인
                        if list_resp.data.next_start_with:
                            next_start = list_resp.data.next_start_with
                        else:
                            break

                    # Byte -> GB 변환
                    size_in_gb = total_size_bytes / (1024 ** 3) if total_size_bytes else 0.0
                    size_str = f"{size_in_gb:.2f}GB"
                    count_str = str(total_count)

                    object_rows.append({
                        "compartment_name": comp_name,
                        "bucket_name": bkt.name,
                        "access_colored": colored_access_str,  # 색상 입힌 접근 권한
                        "tier": tier_str,                     # STANDARD / ARCHIVE 등
                        "approx_size": size_str,              # 직접 계산
                        "approx_count": count_str
                    })

            # 정렬
            object_rows.sort(key=lambda x: (x["compartment_name"].lower(), x["bucket_name"].lower()))

    # -------------------------------------------------------------------------
    # 최종 출력
    # -------------------------------------------------------------------------

    # 1) 인스턴스
    if show_instance:
        inst_table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
        inst_table.add_column("Compartment", style="bold magenta")
        inst_table.add_column("Instance Name", style="bold cyan")
        inst_table.add_column("State", justify="center")
        inst_table.add_column("Subnet")
        inst_table.add_column("NSG")
        inst_table.add_column("Private IP")
        inst_table.add_column("Public IP")
        inst_table.add_column("Shape")
        inst_table.add_column("vCPUs", justify="right")
        inst_table.add_column("Memory(GB)", justify="right")
        inst_table.add_column("Boot Volume", justify="left")
        inst_table.add_column("Block Volumes", justify="left")

        console.print("[bold underline]Instance Info[/bold underline]")
        if instance_rows:
            current_comp = None
            for row in instance_rows:
                if row["compartment_name"] != current_comp:
                    if current_comp is not None:
                        inst_table.add_section()
                    current_comp = row["compartment_name"]

                inst_table.add_row(
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
                    row["boot"],
                    row["block"]
                )
            console.print(inst_table)
        else:
            console.print("(No Instances Matched)")

    # 2) LB
    if show_lb:
        lb_table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
        lb_table.add_column("Compartment", style="bold magenta")
        lb_table.add_column("LB Name", style="bold cyan")
        lb_table.add_column("LB State", justify="center")
        lb_table.add_column("IP Addresses")
        lb_table.add_column("Shape")
        lb_table.add_column("Type")
        lb_table.add_column("Backend Set")
        lb_table.add_column("Backend Target")

        console.print("\n[bold underline]Load Balancer Info[/bold underline]")
        if lb_rows:
            current_comp = None
            for row in lb_rows:
                if row["compartment_name"] != current_comp:
                    if current_comp is not None:
                        lb_table.add_section()
                    current_comp = row["compartment_name"]

                lb_state = row["lb_state"]
                color = lb_state_map.get(lb_state, "white")
                colored_lb_state = f"[{color}]{lb_state}[/{color}]"

                lb_table.add_row(
                    row["compartment_name"],
                    row["lb_name"],
                    colored_lb_state,
                    row["ip_addrs"],
                    row["shape"],
                    row["lb_type"],
                    row["backend_set"],
                    row["backend_target"]
                )
            console.print(lb_table)
        else:
            console.print("(No Load Balancers Matched)")

    # 3) NSG
    if show_nsg:
        nsg_table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
        nsg_table.add_column("Compartment", style="bold magenta")
        nsg_table.add_column("NSG Name", style="bold cyan")
        nsg_table.add_column("Rule Desc", justify="left")
        nsg_table.add_column("Protocol", justify="left")
        nsg_table.add_column("Port Range", justify="left")
        nsg_table.add_column("Source")

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

    # 4) 볼륨 (부팅)
    if show_volume:
        # 4-1) 부팅 볼륨
        boot_table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
        boot_table.add_column("Compartment", style="bold magenta")
        boot_table.add_column("Volume Name", style="bold cyan")
        boot_table.add_column("State", justify="center")
        boot_table.add_column("Size(GB)", justify="right")
        boot_table.add_column("Attached To")

        console.print("\n[bold underline]Boot Volumes[/bold underline]")
        if boot_rows:
            current_comp = None
            for row in boot_rows:
                if row["compartment_name"] != current_comp:
                    if current_comp is not None:
                        boot_table.add_section()
                    current_comp = row["compartment_name"]

                boot_table.add_row(
                    row["compartment_name"],
                    row["volume_name"],
                    row["state"],
                    str(row["size_gb"]),
                    row["attached"]
                )
            console.print(boot_table)
        else:
            console.print("(No Boot Volumes Matched)")

        # 4-2) 블록 볼륨
        block_table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
        block_table.add_column("Compartment", style="bold magenta")
        block_table.add_column("Volume Name", style="bold cyan")
        block_table.add_column("State", justify="center")
        block_table.add_column("Size(GB)", justify="right")
        block_table.add_column("Attached To")

        console.print("\n[bold underline]Block Volumes[/bold underline]")
        if block_rows:
            current_comp = None
            for row in block_rows:
                if row["compartment_name"] != current_comp:
                    if current_comp is not None:
                        block_table.add_section()
                    current_comp = row["compartment_name"]

                block_table.add_row(
                    row["compartment_name"],
                    row["volume_name"],
                    row["state"],
                    str(row["size_gb"]),
                    row["attached"]
                )
            console.print(block_table)
        else:
            console.print("(No Block Volumes Matched)")

    # 5) 오브젝트 스토리지(버킷)
    if show_object:
        obj_table = Table(show_lines=False, box=box.SIMPLE_HEAVY)
        obj_table.add_column("Compartment", style="bold magenta")
        obj_table.add_column("Bucket Name", style="bold cyan")
        obj_table.add_column("Access", justify="left")         # 색상 추가
        obj_table.add_column("Storage Tier", justify="left")   
        obj_table.add_column("Size(GB)", justify="right")      # 직접 계산한 합계
        obj_table.add_column("Object Count", justify="right")  # 직접 계산한 오브젝트 개수

        console.print("\n[bold underline]Object Storage Buckets[/bold underline]")
        if object_rows:
            current_comp = None
            for row in object_rows:
                if row["compartment_name"] != current_comp:
                    if current_comp is not None:
                        obj_table.add_section()
                    current_comp = row["compartment_name"]

                obj_table.add_row(
                    row["compartment_name"],
                    row["bucket_name"],
                    row["access_colored"],
                    row["tier"],
                    row["approx_size"],
                    row["approx_count"]
                )
            console.print(obj_table)
        else:
            console.print("(No Buckets Matched)")


if __name__ == "__main__":
    main()
