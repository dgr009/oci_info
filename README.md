# OCI Info Extended

OCI 인프라 내 인스턴스, 로드 밸런서, NSG, 볼륨, 오브젝트 스토리지 버킷의 정보를 손쉽게 조회할 수 있는 통합 Python CLI 스크립트입니다.

---

## 📁 주요 기능

- **🚀 인스턴스 정보 (`--instance`, `-i`)**
  - 컴파트먼트 별 구분 출력
  - 상태(RUNNING, STOPPED 등)를 컬러로 구분
  - Subnet, NSG, Private/Public IP, vCPU, Memory, 부팅/블록 볼륨 포함

- **🛠️ 로드 밸런서 정보 (`--lb`, `-l`)**
  - IP 주소, Shape, Public/Private 여부
  - Backend Set 및 Backend Instance 정보 포함

- **🔒 NSG 인바운드 룰 (`--nsg`, `-s`)**
  - Protocol, Port Range, Source, Description 등 상세 출력

- **📀 볼륨 정보 (`--volume`, `-v`)**
  - 부팅 볼륨 / 블록 볼륨 구분
  - 각 볼륨의 상태, 용량, 붙어있는 인스턴스 표시

- **📦 오브젝트 스토리지 버킷 정보 (`--object`, `-o`)**
  - 공개 접근 여부 (색상으로 표현)
  - 스토리지 계층
  - 총 오브젝트 수, 총 용량(GB) 계산

---

## ⚙️ 설치 및 의존성

```bash
pip install oci rich
```

> ✅ `~/.oci/config` 에 유효한 프로파일 정보(`tenancy`, `user`, `region`, `key_file` 등)가 필요합니다.

---

## 🔎 사용 예시

```bash
# 모든 리소스 조회 (디폴트)
python3 oci_info.py

# 인스턴스만
python3 oci_info.py --instance

# NSG 와 LB 정보
python3 oci_info.py --nsg --lb

# 오브젝트 스토리지만
python3 oci_info.py --object

# 볼륨 + 오브젝트
python3 oci_info.py -v -o

# 이름 필터링 (myapp 포함된 이름만)
python3 oci_info.py -i --name myapp

# 특정 컴파트먼트 이름 포함 필터링
python3 oci_info.py -c dev
```

---

## 🔐 IAM 권한 정책 예시

다음과 같은 권한이 필요할 수 있습니다:

```text
Allow group YourGroup to inspect instances in tenancy
Allow group YourGroup to read load-balancers in tenancy
Allow group YourGroup to read network-security-groups in tenancy
Allow group YourGroup to read volumes in tenancy
Allow group YourGroup to read boot-volumes in tenancy
Allow group YourGroup to read virtual-network-family in tenancy
Allow group YourGroup to read buckets in tenancy
Allow group YourGroup to manage objects in tenancy where any { request.permission='OBJECT_INSPECT', request.permission='OBJECT_READ' }
```

---

## ✨ 추가 정보

- 모든 테이블은 컴파트먼트 기준으로 그룹핑되어 출력됩니다.
- NSG/볼륨/버킷 등은 별도 섹션으로 나뉘며, 색상으로 상태 표시됩니다.
- 오브젝트 스토리지의 공개 접근 여부(`NoPublicAccess`, `ObjectRead`, `ObjectReadWrite`)는 색상 강조로 표현됩니다.
- Object Storage의 총 사이즈는 `list_objects` API와 `fields="size"`를 이용해 직접 계산합니다.

---

문의나 개선 요청은 언제든 환영합니다 ✨

