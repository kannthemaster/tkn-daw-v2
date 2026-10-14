"""Real local AI + confirmation smoke using Thai aliases in an owned Windows demo.

Reuses the established smoke runner's process ownership, cancellation check,
confirmed CLI Apply/Verify, restoration and cleanup; never attaches to user DAWs.
"""
import json
from pathlib import Path
import sys
from unittest.mock import patch

import windows_intent_smoke as smoke

TEXT = "จาร์วิส หรี่เสียงร้องลงสองดี บี ใส่ EQ ตัดเสียงทุ้ม แล้วบีบเสียงให้เนียนขึ้น"


def main():
    original = smoke.ai.propose
    def propose(_old_text, snapshot, model):
        result = original(TEXT, snapshot, model)
        volumes = [action for action in result['actions'] if action['op'] == 'volume_delta']
        if len(volumes) != 1 or volumes[0]['db'] != -2:
            raise RuntimeError("Normalized request did not produce exactly -2 dB")
        return result
    with patch.object(smoke.ai, 'propose', side_effect=propose):
        status = smoke.main()
    output = smoke.ROOT / 'work/intent-smoke/normalization-request.json'
    output.write_text(json.dumps({'instruction': TEXT, 'status': status,
        'fixture': 'owned disposable no-audio demo', 'real_local_model': True},
        ensure_ascii=False, indent=2), encoding='utf-8')
    return status


if __name__ == '__main__':
    sys.exit(main())
