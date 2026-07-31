ARG BASE_OSG_SERIES=23
ARG BASE_OS=el9
ARG BASE_YUM_REPO=release

FROM opensciencegrid/software-base:$BASE_OSG_SERIES-$BASE_OS-$BASE_YUM_REPO

LABEL maintainer OSG Software <help@osg-htc.org>

# Install dependencies (application, Apache)
RUN \
    yum update -y \
    && yum install -y \
      gcc \
      python3-devel \
      python3-pip \
    && yum install -y \
      httpd \
      httpd-devel \
    && yum clean all && rm -rf /var/cache/yum/* \
    && mkdir /app

# Stolen from https://github.com/opensciencegrid/osgvo-docker-pilot/blob/master/Dockerfile
#
# At Expanse, the admins provided a fixed UID/GID that the container will be run as;
# the app fails to start if this isn't a resolvable username.  For now, create the username
# by hand.  If we hit this at more sites, we can do a for-loop for populating /etc/{passwd,group}
# instead of adding individual user accounts one-by-one.
#
# The Expanse user has such a high UID that it causes problems with people
# running this container using UID namespaces.
# Set NO_EXPANSE_USER when building the image to not add that user.
ARG NO_EXPANSE_USER=
RUN if [ -z "$NO_EXPANSE_USER" ]; then \
        groupadd --gid 12497 g12497 && useradd --gid 12497 --create-home --uid 532362 u532362; \
    fi


WORKDIR /app

# Install application dependencies
COPY pyproject.toml setup.cfg /app/
COPY src /app/src
RUN pip3 install --upgrade pip setuptools && pip3 install --no-cache-dir /app

RUN touch /etc/sysconfig/httpd && mkdir /wsgi && \
    curl -L https://dl.k8s.io/release/v1.24.0/bin/linux/amd64/kubectl > /app/kubectl && \
    chmod +x /app/kubectl

COPY examples/apache.conf /etc/httpd/conf.d/htcondor-autoscale-manager.conf
COPY examples/supervisor-apache.conf /etc/supervisord.d/40-apache.conf
COPY examples/htcondor_autoscale.wsgi /wsgi

EXPOSE 8080/tcp
