"""Exact, source-defined orthogonal outline for phase-one architectural finishes.

No interpolation, slanted edges, inferred dimensions or payment decisions.
A simple closed polygon with no holes can be checked by strict containment of
explicit rectangular installed pieces and openings. Geometry alone never
certifies constructability or source authenticity.
"""
from decimal import Decimal, InvalidOperation

MAX_VERTICES = 64


def number(value, label):
    if isinstance(value, (bool, float)) or not isinstance(value, (int, str, Decimal)):
        raise ValueError(label + ': فقط عدد دقیق مستند مجاز است')
    try:
        num = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(label + ': عدد نامعتبر') from exc
    if (not num.is_finite() or len(num.as_tuple().digits) > 60
            or abs(num.adjusted()) > 60):
        raise ValueError(label + ': مقدار یا دقت غیرمجاز')
    return num


def _crossing(a, b, c, d):
    """True for any point-contact or positive-length intersection of 2 segments."""
    if a[0] == b[0] and c[0] == d[0]:
        return (a[0] == c[0] and max(min(a[1], b[1]), min(c[1], d[1])) <=
                min(max(a[1], b[1]), max(c[1], d[1])))
    if a[1] == b[1] and c[1] == d[1]:
        return (a[1] == c[1] and max(min(a[0], b[0]), min(c[0], d[0])) <=
                min(max(a[0], b[0]), max(c[0], d[0])))
    h1, h2, v1, v2 = (a, b, c, d) if a[1] == b[1] else (c, d, a, b)
    return (min(h1[0], h2[0]) <= v1[0] <= max(h1[0], h2[0]) and
            min(v1[1], v2[1]) <= h1[1] <= max(v1[1], v2[1]))


def checked_outline(raw, length, width):
    """Validate closed, simple, orthogonal source polygon in a known rectangle."""
    length = number(length, 'طول وجه')
    width = number(width, 'عرض وجه')
    if length <= 0 or width <= 0:
        raise ValueError('ابعاد مثبت وجه لازم است')
    if not isinstance(raw, list) or not 5 <= len(raw) <= MAX_VERTICES + 1:
        raise ValueError('حداقل چهار ضلع و حداکثر ۶۴ رأس با حلقه بسته لازم است')
    coords = []
    for item in raw:
        if not isinstance(item, dict) or set(item) != {'x', 'y'}:
            raise ValueError('رأس باید فقط مختصات x و y مستند داشته باشد')
        point = (number(item['x'], 'مختصات X'), number(item['y'], 'مختصات Y'))
        if not (0 <= point[0] <= length and 0 <= point[1] <= width):
            raise ValueError('رأس خارج از محدوده وجه است')
        coords.append(point)
    if coords[-1] != coords[0] or len(set(coords[:-1])) != len(coords) - 1:
        raise ValueError('چندضلعی باید یک حلقه بسته و بدون رأس تکراری باشد')
    vertices = coords[:-1]
    n = len(vertices)
    segments = []
    for i in range(n):
        a, b = vertices[i], vertices[(i + 1) % n]
        if (a[0] == b[0]) == (a[1] == b[1]):
            raise ValueError('هر ضلع باید افقی یا قائم و دارای طول مثبت باشد')
        c = vertices[(i + 2) % n]
        if (a[0] == b[0]) == (b[0] == c[0]):
            raise ValueError('رأس میانی زائد/هم‌راستا مجاز نیست')
        segments.append((a, b))
    for i in range(n):
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            if _crossing(*segments[i], *segments[j]):
                raise ValueError('خودتقاطعی یا تماس غیرمجاز در مرز چندضلعی')
    if (min(p[0] for p in vertices) != 0 or min(p[1] for p in vertices) != 0
            or max(p[0] for p in vertices) != length
            or max(p[1] for p in vertices) != width):
        raise ValueError('ابعاد کادر محدودکننده با رئوس واقعی برابر نیست')
    twice = sum((vertices[i][0] * vertices[(i + 1) % n][1] -
                 vertices[(i + 1) % n][0] * vertices[i][1] for i in range(n)), Decimal(0))
    if twice == 0:
        raise ValueError('مساحت چندضلعی صفر است')
    return tuple(vertices), abs(twice) / Decimal(2)


def _inside(point, vertices):
    x, y = point
    crossings = 0
    for a, b in zip(vertices, vertices[1:] + vertices[:1]):
        if a[0] == b[0] and min(a[1], b[1]) < y < max(a[1], b[1]) and a[0] > x:
            crossings += 1
    return bool(crossings % 2)


def rectangle_inside(vertices, box):
    """Check full positive-area inclusion; edge contact is allowed, leaks aren't."""
    x1, y1, x2, y2 = box
    if x1 >= x2 or y1 >= y2:
        return False
    xs = sorted({x1, x2} | {x for x, _ in vertices if x1 < x < x2})
    ys = sorted({y1, y2} | {y for _, y in vertices if y1 < y < y2})
    expected = (x2 - x1) * (y2 - y1)
    covered = Decimal(0)
    for x0, x3 in zip(xs, xs[1:]):
        for y0, y3 in zip(ys, ys[1:]):
            if _inside(((x0 + x3) / 2, (y0 + y3) / 2), vertices):
                covered += (x3 - x0) * (y3 - y0)
    return covered == expected
