# Base: Ubuntu 24.04 LTS
FROM ubuntu:24.04

# Evitar prompts interactivos durante la instalación de paquetes
ENV DEBIAN_FRONTEND=noninteractive

# 1. Instalar dependencias (Corregido: octave-dev en lugar de liboctave-dev)
RUN apt-get update && apt-get install -y \
    build-essential cmake git libhdf5-dev libvtk9-dev \
    libboost-all-dev libcgal-dev libtinyxml-dev \
    qtbase5-dev libvtk9-qt-dev \
    octave octave-dev pkg-config\
    python3-pip python3-venv python3-setuptools python3-setuptools-scm \
    python3-numpy python3-matplotlib python3-h5py \
    paraview \
    gengetopt help2man groff pod2pdf bison flex libhpdf-dev libtool \
    && rm -rf /var/lib/apt/lists/*

# 2. Configurar el Entorno Virtual (venv) para Python
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 3. Descargar y compilar openEMS
WORKDIR /opt
RUN git clone --recursive https://github.com/thliebig/openEMS-Project.git && \
    cd openEMS-Project && \
    ./update_openEMS.sh /opt/openEMS

# 4. Variables de entorno de openEMS (Corregidos los warnings)
ENV OPENEMS_PATH=/opt/openEMS
ENV PATH=$OPENEMS_PATH/bin:$PATH
ENV LD_LIBRARY_PATH=$OPENEMS_PATH/lib
ENV PYTHONPATH=$OPENEMS_PATH/share/CSXCAD/python:$OPENEMS_PATH/share/openEMS/python

# 5. Instalar Jupyter Lab y dependencias científicas extra
RUN pip install --no-cache-dir jupyterlab pandas scipy matplotlib

ENV CPATH=/opt/openEMS/include
ENV LIBRARY_PATH=/opt/openEMS/lib
ENV PKG_CONFIG_PATH=/opt/openEMS/lib/pkgconfig


RUN pip install /opt/openEMS-Project/CSXCAD/python
RUN pip install /opt/openEMS-Project/openEMS/python

# 6. Directorio de trabajo
WORKDIR /work

# Exponer el puerto de Jupyter
EXPOSE 8888

# Arrancar Jupyter Lab al iniciar el contenedor
CMD ["jupyter", "lab", "--ip=0.0.0.0", "--port=8888", "--no-browser", "--allow-root", "--NotebookApp.token=''"]
