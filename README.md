# oci_info_extended.py

**OCI 정보 조회(인스턴스, LB, NSG)를 한 번에 할 수 있는 Python 스크립트**

---

## 기능 요약
- **인스턴스 정보**:
  - 컴파트먼트별로 인스턴스 나열
  - 종료된(TERMINATED) 인스턴스 제외
  - vCPU(= OCPU × 2), 메모리(GB) 확인
  - Private IP / Public IP, Subnet, NSG, 부팅 볼륨 크기, 블록 볼륨 크기
  - 인스턴스 상태를 색깔(RUNNING=Green 등)로 표시
- **로드 밸런서(LB)**
  - 컴파트먼트별 LB 이름, IP 주소 목록, Shape, Public/Private 여부
  - 백엔드셋과 그 백엔드(인스턴스) 목록
  - LB 상태(Active, Provisioning, Failed 등)를 컬러로 구분
- **NSG**(Network Security Group)
  - 컴파트먼트별 NSG 목록
  - **Inbound** 룰(Protocol, Port Range, Source, Rule Desc 등)

---

## 설치 및 준비
1. **Python 3.6 이상** 환경
2. [OCI Python SDK](https://oracle-cloud-infrastructure-python-sdk.readthedocs.io/en/latest/)와 `rich` 라이브러리:
   ```bash
   pip install oci rich
   ```
3. **OCI 설정 파일**: `~/.oci/config`
   - `DEFAULT` 프로파일에 적절한 인증 정보 필요 (User OCID, Key, Region 등)

---

## 실행 방법

```bash
python3 oci_info_extended.py [OPTIONS]
```

### 주요 옵션
- `--instance, -i`: 인스턴스 정보만 출력
- `--lb, -l`: 로드 밸런서 정보만 출력
- `--nsg`: NSG 인바운드 룰만 출력
- **옵션을 지정하지 않으면** 인스턴스, LB, NSG **모두** 출력

### 이름 필터(`--name`)
- `--name <filter_text>`: 해당 텍스트가 포함된 리소스 이름만 표시 (대소문자 구분 없음)
- 예) `-i --name foo` → **인스턴스** 중 이름에 `foo`가 들어간 항목만 표시
- 여러 옵션을 함께 사용 시 **각각의 리소스**에 동일하게 이름 필터가 적용됩니다.

#### 예시
1. **전부 조회**:
   ```bash
   python3 oci_info_extended.py
   ```
2. **인스턴스만**:
   ```bash
   python3 oci_info_extended.py --instance
   # 또는
   python3 oci_info_extended.py -i
   ```
3. **LB, NSG만**:
   ```bash
   python3 oci_info_extended.py --lb --nsg
   # 또는
   python3 oci_info_extended.py -l --nsg
   ```
4. **인스턴스 중 이름에 "my-instance" 포함**:
   ```bash
   python3 oci_info_extended.py -i --name my-instance
   ```

---

## 권한 (IAM Policy)
OCI 클라이언트를 통해 리소스를 조회하려면 **해당 리소스들에 대한 읽기 권한**이 있어야 합니다.

예를 들어:
```text
Allow group <YourGroup> to inspect instances in tenancy
Allow group <YourGroup> to read load-balancers in tenancy
Allow group <YourGroup> to read network-security-groups in tenancy
Allow group <YourGroup> to read volumes in tenancy
Allow group <YourGroup> to read boot-volumes in tenancy
Allow group <YourGroup> to read virtual-network-family in tenancy
```
(실제 정책은 환경에 맞춰 적용하세요.)

---

## 기타 사항
- 인스턴스별 VNIC이 여러 개인 경우, 첫 번째 VNIC만 표시합니다.
- 각 컴파트먼트별로 **구분선**을 둬서 정보를 가독성 있게 구분합니다.
- `state_color_map`, `lb_state_color_map`에서 상태별 컬러를 변경할 수 있습니다.
- 추가 확장(예: 보안 규칙 Outbound 룰, 여러 VNIC 표시 등)은 코드를 수정해서 적용 가능합니다.

문제나 개선점이 있으면 언제든 알려주세요!
