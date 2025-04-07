# oci_info.py

Oracle Cloud Infrastructure(OCI) 환경에서 모든 컴파트먼트 내 인스턴스 정보를 수집하여 보기 좋게 출력하는 Python 스크립트입니다.

## ✅ 기능 설명
이 스크립트는 다음 정보를 **Rich Table** 형식으로 출력합니다:

- 구획(Compartment) 이름별 구분 출력
- 인스턴스 이름
- 서브넷 이름
- 네트워크 보안 그룹(NSG)
- Private IP
- Public IP
- 인스턴스 Shape
- vCPU 수
- 메모리 크기 (GB)
- 부팅 볼륨 크기 (GB)
- 블록 볼륨 크기 (GB)

## 📁 의존 라이브러리
다음 라이브러리가 설치되어 있어야 합니다:

```bash
pip install oci rich
```

## ⚙️ 사용 방법
1. `~/.oci/config` 파일이 존재하고 유효한 `DEFAULT` 프로파일이 설정되어 있어야 합니다.
2. 실행:

```bash
python3 oci_info.py
```

3. 결과는 터미널에 Rich Table 형식으로 출력됩니다.

## 📦 파일 구조
- `oci_info.py`: 메인 실행 스크립트
- `readme.md`: 사용 설명서

## 🔐 필수 권한 (IAM Policy)
스크립트가 정상 작동하려면 다음 리소스들에 대해 읽기 권한이 필요합니다:

- `inspect instances`
- `read boot-volumes`
- `read volumes`
- `read vnics`
- `read subnets`
- `read network-security-groups`

예시 정책:
```text
Allow group YourGroupName to inspect instances in tenancy
Allow group YourGroupName to read boot-volumes in tenancy
Allow group YourGroupName to read volumes in tenancy
Allow group YourGroupName to read virtual-network-family in tenancy
```

## 🙋 기타 참고사항
- 부팅 볼륨은 `list_boot_volume_attachments()`와 `get_boot_volume()`을 조합하여 추출합니다.
- 블록 볼륨은 `list_volume_attachments()`와 `get_volume()`을 사용하여 추출합니다.
- 종료된 인스턴스(TERMINATED)는 제외됩니다.
- 컴파트먼트 별로 그룹화되어 출력됩니다.

---

문의 또는 개선 제안은 언제든 환영입니다!