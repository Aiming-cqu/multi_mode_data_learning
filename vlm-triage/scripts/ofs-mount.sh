#!/bin/sh

set -eux

rerun_with_root()
{
	if [ "$(id -u)" != 0 ]
	then
		exec sudo -E nice -n -9 "$0" "$@"
		exit 0
	fi
}

export MOUNT_DATA="${MOUNT_DATA:-${HOME}/mount-data}"
export MOUNT_ENV="${MOUNT_ENV:-${HOME}/mount-env}"

if [ -f /mnt/common/jianshu/ofs/release/current/script/ofs_mount.sh ]
then
	rerun_with_root
	bash /mnt/common/jianshu/ofs/release/current/script/ofs_mount.sh te-ds-autolabeling-dos-1 "${MOUNT_DATA}" b97966f706a84264a99eeb53aba6a698 nmgpu
	bash /mnt/common/jianshu/ofs/release/current/script/ofs_mount.sh te-ds-autolabeling-dos-2 "${MOUNT_ENV}" 29996d1bb1b849228e92732bc9c21093 hbbpussd
	echo -1000 | tee $(pgrep -f orangefs | xargs -I{} echo /proc/{}/oom_score_adj)
else
	export OFS_EXE="${OFS_EXE:-$(command -v orangefs)}"
	rerun_with_root
	OFS_LOG_DIR="${OFS_LOG_DIR:-/var/log}"
	mkdir -p "${OFS_LOG_DIR}/"
	touch "${OFS_LOG_DIR}/orangefs.te-ds-autolabeling-dos-1.log" "${OFS_LOG_DIR}/orangefs.te-ds-autolabeling-dos-2.log"
	chmod a+r "${OFS_LOG_DIR}/orangefs.te-ds-autolabeling-dos-1.log" "${OFS_LOG_DIR}/orangefs.te-ds-autolabeling-dos-2.log"
	nohup "${OFS_EXE}" posix mount --rs-addr=10.66.96.18:8030 --token=b97966f706a84264a99eeb53aba6a698 --volume-name=te-ds-autolabeling-dos-1 --mount-point="${MOUNT_DATA}" >"${OFS_LOG_DIR}/orangefs.te-ds-autolabeling-dos-1.log" 2>&1 &
	nohup "${OFS_EXE}" posix mount --rs-addr=10.66.96.43:8030 --token=29996d1bb1b849228e92732bc9c21093 --volume-name=te-ds-autolabeling-dos-2 --mount-point="${MOUNT_ENV}" >"${OFS_LOG_DIR}/orangefs.te-ds-autolabeling-dos-2.log" 2>&1 &
fi
