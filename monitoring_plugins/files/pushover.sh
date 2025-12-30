#!/usr/bin/env bash

curl -s \
  --form-string "token=${token}" \
  --form-string "user=${user}" \
  --form-string "message=${message}" \
  --form-string "title=${title}" \
  https://api.pushover.net/1/messages.json
