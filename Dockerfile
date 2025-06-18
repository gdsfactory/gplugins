FROM --platform=linux/amd64 ghcr.io/astral-sh/uv:python3.11-bookworm-slim

# Install system dependencies including KLayout
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    make \
    cmake \
    git \
    build-essential \
    libpng-dev \
    libcurl4-openssl-dev \
    libexpat1-dev \
    python3-dev \
    klayout \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Miniconda
RUN wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && \
    bash /tmp/miniconda.sh -b -p /opt/conda && \
    rm /tmp/miniconda.sh

# Add conda to PATH
ENV PATH="/opt/conda/bin:${PATH}"

# Create conda environment with Python 3.11 (matching the base image)
RUN conda create -n pymeep python=3.11 -y
RUN echo "source activate pymeep" >> ~/.bashrc
ENV PATH="/opt/conda/envs/pymeep/bin:${PATH}"

# Install conda packages in the pymeep environment
RUN conda install -n pymeep -c conda-forge pymeep=*=mpi_mpich_* nlopt -y

# Create and activate uv virtual environment
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app
COPY . .

# Install the rest of your requirements
RUN uv pip install -e ".[dev,docs,femwell,gmsh,meow,sax,tidy3d,klayout,vlsir]"

USER non-root

# Set the default command
CMD ["bash"]
