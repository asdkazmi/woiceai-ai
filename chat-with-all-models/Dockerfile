FROM nvidia/cuda:12.2.0-base-ubuntu20.04

# Install Python 3.11 from the official Python image
FROM python:3.11-slim

# Use the official CUDA 12.2 base image

# Set environment variables for non-interactive installations
ENV DEBIAN_FRONTEND=noninteractive

# Install necessary packages and CUDA toolkit
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    curl \
    gnupg2 \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Add CUDA repository key
RUN apt-key adv --fetch-keys https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/3bf863cc.pub

# Add CUDA repository to apt sources list
RUN echo "deb https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2004/x86_64/ /" \
    > /etc/apt/sources.list.d/cuda.list

# Install CUDA Toolkit 12.2
RUN apt-get update && apt-get install -y --no-install-recommends \
    cuda-toolkit-12-2 \
    && rm -rf /var/lib/apt/lists/*

# Set the CUDA environment variables
ENV PATH /usr/local/cuda-12.2/bin:${PATH}
ENV LD_LIBRARY_PATH /usr/local/cuda-12.2/lib64:${LD_LIBRARY_PATH}

# Verify the CUDA installation
RUN nvcc --version

RUN apt-get update && apt-get install git-lfs -y
RUN git lfs install

WORKDIR /

RUN pip install --upgrade pip

RUN pip3 install --upgrade pip && \
    pip3 install llama-cpp-python==0.2.90 \
    --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu122

RUN pip3 install packaging
RUN pip3 install torch==2.4.1

COPY requirements.txt .
RUN pip3 install --default-timeout=300 -r requirements.txt

RUN GIT_LFS_SKIP_SMUDGE=1 git clone https://huggingface.co/dunzhang/stella_en_400M_v5
RUN curl -L https://huggingface.co/dunzhang/stella_en_400M_v5/resolve/main/2_Dense_1024/model.safetensors \
    -o stella_en_400M_v5/2_Dense_1024/model.safetensors
RUN curl -L https://huggingface.co/dunzhang/stella_en_400M_v5/resolve/main/model.safetensors \
    -o stella_en_400M_v5/model.safetensors

COPY merged-q4_k_m-model.gguf  .
COPY Meta-Llama-3.1-8B-Instruct-gptq  Meta-Llama-3.1-8B-Instruct-gptq


ENV HF_DATASETS_CACHE="/runpod-volume/datasets"
ENV HUGGINGFACE_HUB_CACHE="/runpod-volume/hub"
ENV TRANSFORMERS_CACHE="/runpod-volume/hub"
ENV HF_HUB_OFFLINE=1

COPY src/ .
COPY .env .
CMD [ "python3", "-u", "/handler.py" ]
