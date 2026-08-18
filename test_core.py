from mapper import convert_layout
from detector import detect_wrong_layout

CASES = [
    ('akuo nv eurv', 'שלום מה קורה'),
    ('tbh rumv kf,uc ntus', 'אני רוצה לכתוב מאוד'),
]

for raw, expected in CASES:
    converted = convert_layout(raw)
    print(raw, '=>', converted)
    assert converted == expected, (converted, expected)

print('mapper tests passed')

samples = [
    'akuo nv eurv tbh rumv kf,uc',
    'hello this is a perfectly normal english sentence',
    'שלום זה משפט עברי רגיל לחלוטין',
]
for s in samples:
    print('DETECT:', s, '=>', detect_wrong_layout(s))
