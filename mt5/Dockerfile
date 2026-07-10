FROM gmag11/metatrader5_vnc@sha256:2fdff449cf70b74c242319828b6859592ab52dfb05690d9a989c75107dabf4c1

USER root

ARG MT5LINUX_WHEEL_URL="https://files.pythonhosted.org/packages/61/92/4e5cf23e272de106c83058a54f6bfa51b46a6e6a93cc524d81ae102a0b9b/mt5linux-0.1.9-py3-none-any.whl"
ARG MT5LINUX_WHEEL_SHA256="6cafa7f4b95470aa62877e1989c03be04f20d786d55f94e92aaefa1bf084e802"
ARG RPYC_WHEEL_URL="https://files.pythonhosted.org/packages/3f/99/2e119d541d596daea39643eb9312b47c7847383951300f889166938035b1/rpyc-6.0.2-py3-none-any.whl"
ARG RPYC_WHEEL_SHA256="8072308ad30725bc281c42c011fc8c922be15f3eeda6eafb2917cafe1b6f00ec"
ARG PLUMBUM_WHEEL_URL="https://files.pythonhosted.org/packages/6c/fc/6cdaf59a001c707333869b054daf1e0df02978d261f20f8b082afcf189c3/plumbum-1.7.0-py2.py3-none-any.whl"
ARG PLUMBUM_WHEEL_SHA256="139bbe08ee065b522a8a07d4f7e9f8eddffd78cc218b65b11cca2b33683e6b57"
ARG NUMPY_WHEEL_URL="https://files.pythonhosted.org/packages/02/03/74fe2a4cb3817d94d86402f2506554130a2f01414e299b5a843e5a8a957f/numpy-2.4.6-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
ARG NUMPY_WHEEL_SHA256="89cd468399cfd2504718f0ba50e410dca55a170b61a02ad92bb18c8a65186e93"
ARG WINE_NUMPY_WHEEL_URL="https://files.pythonhosted.org/packages/28/7d/4b92e2fe20b214ffca36107f1a3e75ef4c488430e64de2d9af5db3a4637d/numpy-1.26.4-cp39-cp39-win32.whl"
ARG WINE_NUMPY_WHEEL_SHA256="a354325ee03388678242a4d7ebcd08b5c727033fcff3b2f536aea978e15ee9e6"

RUN install -d -m 0755 /opt/mt5-hardening \
    && curl --fail --silent --show-error --location \
        "$MT5LINUX_WHEEL_URL" \
        --output /opt/mt5-hardening/mt5linux-0.1.9-py3-none-any.whl \
    && curl --fail --silent --show-error --location \
        "$RPYC_WHEEL_URL" \
        --output /opt/mt5-hardening/rpyc-6.0.2-py3-none-any.whl \
    && curl --fail --silent --show-error --location \
        "$PLUMBUM_WHEEL_URL" \
        --output /opt/mt5-hardening/plumbum-1.7.0-py2.py3-none-any.whl \
    && curl --fail --silent --show-error --location \
        "$NUMPY_WHEEL_URL" \
        --output /opt/mt5-hardening/numpy-2.4.6-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl \
    && curl --fail --silent --show-error --location \
        "$WINE_NUMPY_WHEEL_URL" \
        --output /opt/mt5-hardening/numpy-1.26.4-cp39-cp39-win32.whl \
    && printf '%s  %s\n%s  %s\n%s  %s\n%s  %s\n%s  %s\n' \
        "$MT5LINUX_WHEEL_SHA256" /opt/mt5-hardening/mt5linux-0.1.9-py3-none-any.whl \
        "$RPYC_WHEEL_SHA256" /opt/mt5-hardening/rpyc-6.0.2-py3-none-any.whl \
        "$PLUMBUM_WHEEL_SHA256" /opt/mt5-hardening/plumbum-1.7.0-py2.py3-none-any.whl \
        "$NUMPY_WHEEL_SHA256" /opt/mt5-hardening/numpy-2.4.6-cp311-cp311-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl \
        "$WINE_NUMPY_WHEEL_SHA256" /opt/mt5-hardening/numpy-1.26.4-cp39-cp39-win32.whl \
        | sha256sum -c -

COPY patch-start.py /opt/mt5-hardening/patch-start.py
RUN python3 /opt/mt5-hardening/patch-start.py \
    && rm /opt/mt5-hardening/patch-start.py
