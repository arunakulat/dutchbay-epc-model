FROM mcr.microsoft.com/devcontainers/python:1-3.12-bookworm@sha256:7876580dc67fd460fd962f004cbeb480027e9bbc0657096f1087db11f9eaff39

COPY .devcontainer/install_audit_review_sshd.sh /tmp/install_audit_review_sshd.sh
COPY .devcontainer/ssh_entrypoint.sh /usr/local/sbin/dutchbay-ssh-entrypoint.sh
COPY .devcontainer/start_audit_review_sshd.sh /usr/local/sbin/dutchbay-sshd-start.sh
COPY .devcontainer/sshd_readiness.py /usr/local/lib/dutchbay/sshd_readiness.py

RUN chmod 0755 /tmp/install_audit_review_sshd.sh \
    && /tmp/install_audit_review_sshd.sh \
    && rm -- /tmp/install_audit_review_sshd.sh \
    && chmod 0755 /usr/local/sbin/dutchbay-ssh-entrypoint.sh \
    && chmod 0755 /usr/local/sbin/dutchbay-sshd-start.sh \
    && chmod 0644 /usr/local/lib/dutchbay/sshd_readiness.py

ENTRYPOINT ["/usr/local/sbin/dutchbay-ssh-entrypoint.sh"]
CMD ["/usr/bin/sleep", "infinity"]
