#!/bin/sh
cat <<EOF > ./tmp/_.json
{
  "input": {
    "text": "$1"
  },
  "voice": {
    "languageCode": "ja-JP",
    "name": "ja-JP-Neural2-B"
  },
  "audioConfig": {
    "audioEncoding": "MP3",
    "pitch": 4
  }
}
EOF
curl -s -X POST -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" -H "Content-Type: application/json" -d @./tmp/_.json https://texttospeech.googleapis.com/v1/text:synthesize | jq -r .audioContent | base64 -d > ./tmp/_.mp3
echo "$(pwd)/tmp/_.mp3"
