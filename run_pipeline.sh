#!/bin/bash

# =============================================================================
# 한국어 음성 분석 파이프라인 실행 스크립트 (Linux/Mac)
# =============================================================================

set -e  # 오류 발생 시 스크립트 중단

# 색상 코드 정의
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 함수 정의
print_header() {
    echo -e "${CYAN}================================================================================================${NC}"
    echo -e "${CYAN}한국어 음성 분석 파이프라인${NC}"
    echo -e "${CYAN}S3 → 변환 → 한국어 분석 → STT → GPT 평가 → MongoDB/MariaDB 저장${NC}"
    echo -e "${CYAN}================================================================================================${NC}"
}

print_step() {
    echo -e "\n${BLUE}$1${NC}"
}

print_success() {
    echo -e "${GREEN}$1${NC}"
}

print_error() {
    echo -e "${RED}$1${NC}"
}

print_warning() {
    echo -e "${YELLOW}$1${NC}"
}

# 메인 실행
main() {
    print_header
    
    # 1. 현재 디렉토리 확인
    print_step "현재 작업 디렉토리 확인"
    if [[ ! -f "run_pipeline.py" ]]; then
        print_error "run_pipeline.py 파일을 찾을 수 없습니다. 프로젝트 루트 디렉토리에서 실행해주세요."
        exit 1
    fi
    print_success "프로젝트 루트 디렉토리 확인 완료"
    
    # 2. Conda 환경 확인 및 활성화
    print_step "Conda 환경 'ko_pipeline' 활성화 중"
    
    # Conda 초기화
    if [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
        source "$HOME/miniconda3/etc/profile.d/conda.sh"
    elif [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
        source "$HOME/anaconda3/etc/profile.d/conda.sh"
    elif [[ -f "/opt/anaconda3/etc/profile.d/conda.sh" ]]; then
        source "/opt/anaconda3/etc/profile.d/conda.sh"
    elif [[ -f "/usr/local/anaconda3/etc/profile.d/conda.sh" ]]; then
        source "/usr/local/anaconda3/etc/profile.d/conda.sh"
    else
        print_error "Conda를 찾을 수 없습니다. Conda가 설치되어 있는지 확인해주세요."
        exit 1
    fi
    
    # ko_pipeline 환경 확인
    if conda env list | grep -q "ko_pipeline"; then
        conda activate ko_pipeline
        print_success "ko_pipeline 환경 활성화 완료"
    else
        print_error "ko_pipeline conda 환경을 찾을 수 없습니다."
        echo "다음 명령어로 환경을 생성해주세요:"
        echo "conda create -n ko_pipeline python=3.9"
        echo "conda activate ko_pipeline"
        echo "pip install -r requirements.txt"
        exit 1
    fi
    
    # 3. Python 및 패키지 확인
    print_step "Python 환경 및 필수 패키지 확인"
    
    python --version
    
    # 필수 패키지 확인
    required_packages=("fastapi" "librosa" "openai" "boto3" "motor" "aiomysql" "transformers")
    for package in "${required_packages[@]}"; do
        if python -c "import $package" 2>/dev/null; then
            echo -e "  ${GREEN}$package${NC}"
        else
            print_error "$package 패키지가 설치되지 않았습니다."
            echo "pip install -r requirements.txt 를 실행해주세요."
            exit 1
        fi
    done
    print_success "필수 패키지 확인 완료"
    
    # 4. 환경변수 파일 확인
    print_step "환경변수 설정 확인"
    
    if [[ ! -f ".env" ]]; then
        print_error ".env 파일을 찾을 수 없습니다."
        if [[ -f ".env.example" ]]; then
            echo "다음 명령어로 .env 파일을 생성하고 설정을 완료해주세요:"
            echo "cp .env.example .env"
            echo "그 후 .env 파일을 편집하여 필요한 값들을 설정해주세요."
        else
            echo ".env.example 파일을 참고하여 .env 파일을 생성해주세요."
        fi
        exit 1
    fi
    print_success ".env 파일 확인 완료"
    
    # 5. FFmpeg 확인
    print_step "FFmpeg 설치 확인"
    
    if command -v ffmpeg &> /dev/null; then
        ffmpeg_version=$(ffmpeg -version | head -n1)
        print_success "FFmpeg 설치 확인: $ffmpeg_version"
    else
        print_warning "FFmpeg가 설치되지 않았습니다."
        echo "오디오 변환을 위해 FFmpeg 설치를 권장합니다:"
        echo "  Ubuntu/Debian: sudo apt install ffmpeg"
        echo "  CentOS/RHEL: sudo yum install ffmpeg"
        echo "  macOS: brew install ffmpeg"
        echo ""
        echo "FFmpeg 없이도 실행할 수 있지만, 일부 오디오 형식 변환에 제한이 있을 수 있습니다."
        read -p "계속 진행하시겠습니까? (y/N): " continue_without_ffmpeg
        if [[ ! "$continue_without_ffmpeg" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
    
    # 6. 디스크 공간 확인
    print_step "디스크 공간 확인"
    
    available_space=$(df . | tail -1 | awk '{print $4}')
    if [[ $available_space -lt 1048576 ]]; then  # 1GB 미만
        print_warning "사용 가능한 디스크 공간이 1GB 미만입니다."
        echo "대용량 오디오 파일 처리 시 공간이 부족할 수 있습니다."
        read -p "계속 진행하시겠습니까? (y/N): " continue_low_space
        if [[ ! "$continue_low_space" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    else
        print_success "충분한 디스크 공간 확인"
    fi
    
    # 7. 최종 확인 및 실행
    print_step "파이프라인 실행 준비 완료"
    
    echo -e "\n${PURPLE}모든 사전 검사를 통과했습니다!${NC}"
    echo -e "${PURPLE}파이프라인을 시작합니다...${NC}\n"
    
    # 파이프라인 실행
    python run_pipeline.py
    
    # 실행 결과 확인
    if [[ $? -eq 0 ]]; then
        echo -e "\n${GREEN}파이프라인이 성공적으로 완료되었습니다!${NC}"
    else
        echo -e "\n${RED}파이프라인 실행 중 오류가 발생했습니다.${NC}"
        exit 1
    fi
}

# 스크립트 실행 시작
main "$@" 