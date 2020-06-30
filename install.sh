#!/bin/sh

DEST="${HOME}/.config/mpv/scripts"
mkdir -p "${DEST}"

for file in $(echo "interSubs_config.py interSubs.lua interSubs.py")
do
  dest="${DEST}/${file}"
  if [[ ! -L ${dest} ]]
  then
    ln -s "${PWD}/${file}" ${dest}
    echo "${dest} linked"
  else
    echo "${dest} existed"
  fi
done
