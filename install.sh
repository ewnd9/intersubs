#!/bin/bash

SCRIPTS="${HOME}/.config/mpv/scripts"
mkdir -p "${SCRIPTS}"

link () {
  local src=$1
  local dest=$2

  if [[ ! -L ${dest} ]]
  then
    ln -s "${src}" "${dest}"
    echo "${dest} linked"
  else
    echo "${dest} existed"
  fi
}

for file in $(ls intersubs)
do
  link "${PWD}/intersubs/${file}" "${SCRIPTS}/${file}"
done

for file in $(ls intersubs.lua)
do
  link "${PWD}/${file}" "${SCRIPTS}/${file}"
done
