"""Refine sanitized Codex field presentations; never reads original raw archives.
Usage: python script.py V1_FULL_DIR PRIOR_REDUCED_DIR OUTPUT_DIR
All body extraction is checked against prior full_safe_sha256. Exact earlier
strings can be referenced with an explicitly retained terminal-newline suffix.
Output shorter than prior only; every JSON wrapper leaf retained. Does not
claim semantic reads. Input status fields carry through unchanged.
"""
from pathlib import Path
import json, hashlib, sys
v1, prior_dir, out = map(Path, sys.argv[1:4])
assert out not in (v1, prior_dir)
out.mkdir(exist_ok=True)
full_fields = json.loads((v1 / 'fields.json').read_text())
prior_fields = json.loads((prior_dir / 'fields.json').read_text())
full_text = (v1 / 'review.txt').read_text()
prior_text = (prior_dir / 'review.txt').read_text()
known, chunks, fields, changes = {}, [], [], []
offset = 0

def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()

def flatten(value, path='$'):
    if isinstance(value, dict):
        return '\n'.join(flatten(x, path + '.' + k) for k, x in value.items()) or path + ' = {}'
    if isinstance(value, list):
        return '\n'.join(flatten(x, path + f'[{j}]') for j, x in enumerate(value)) or path + ' = []'
    return path + ' = ' + (value if isinstance(value, str) else json.dumps(value))

for original, previous in zip(full_fields, prior_fields):
    assert original['display'] == previous['display']
    framed = full_text[slice(*original['range'])].split('=====\n', 1)[1]
    matches = [framed[:-i] if i else framed for i in range(10)
               if sha(framed[:-i] if i else framed) == previous['full_safe_sha256']]
    assert len(matches) == 1, previous['display']
    body, index = matches[0], previous['display']
    prior = prior_text[slice(*previous['range'])]
    refs = []

    def transform(value, path='$'):
        if isinstance(value, str):
            trimmed = value.rstrip('\n')
            exact, short = sha(value), sha(trimmed)
            if len(value) > 100 and (exact in known or short in known):
                key = exact if exact in known else short
                reference = known[key]
                suffix = '' if key == exact else value[len(trimmed):]
                refs.append({'path': path, 'target_sha256': exact,
                             'reference': reference, 'exact_suffix': suffix})
                return ('[EXACT earlier decoded string ' + reference + '; targetSHA=' + exact
                        + '; literal appended suffix=' + json.dumps(suffix) + ']')
            return value
        if isinstance(value, dict):
            return {k: transform(x, path + '.' + k) for k, x in value.items()}
        if isinstance(value, list):
            return [transform(x, path + f'[{j}]') for j, x in enumerate(value)]
        return value

    def collect(value, path='$'):
        if isinstance(value, str) and len(value) > 100:
            known.setdefault(sha(value), f'display{index}:{path}')
        elif isinstance(value, dict):
            for key, item in value.items():
                collect(item, path + '.' + key)
        elif isinstance(value, list):
            for j, item in enumerate(value):
                collect(item, path + f'[{j}]')

    try:
        decoded = json.loads(body)
    except (ValueError, TypeError):
        decoded = None
    text, row = prior, dict(previous)
    if isinstance(decoded, (dict, list)):
        normalized = (prior.split('=====\n', 1)[0] + '=====\n'
                      + '[Lossless JSON field decoding; wrapper fields retained]\n'
                      + flatten(transform(decoded)) + '\n')
        if len(normalized) < len(prior):
            text = normalized
            row['decoded_json_references'] = refs
            changes.append({'display': index, 'old_chars': len(prior),
                            'new_chars': len(text), 'references': refs})
        collect(decoded)
    known.setdefault(sha(body), f'display{index}:$FULL')
    row.update(range=[offset, offset + len(text)], presentation_sha256=sha(text))
    fields.append(row)
    chunks.append(text)
    offset += len(text)

assert len(fields) == len(prior_fields) == len(full_fields)
(out / 'fields.json').write_text(json.dumps(fields, indent=2) + '\n')
(out / 'review.txt').write_text(''.join(chunks))
(out / 'decoded-json-references.json').write_text(json.dumps(changes, indent=2) + '\n')
for name in ['records.json', 'omissions.json']:
    (out / name).write_bytes((prior_dir / name).read_bytes())
manifest = json.loads((prior_dir / 'manifest.json').read_text())
manifest.update(review_chars=offset, refinement='Lossless JSON leaf decoding and exact earlier string references; terminal newline suffix explicit; all wrapper leaves retained; shorter presentation only.')
(out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(json.dumps({'fields': len(fields), 'decoded_fields': len(changes),
                  'review_chars': offset, 'saved_chars': len(prior_text) - offset}))
