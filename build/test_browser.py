#!/usr/bin/env python3
"""Tests for the interactions on timeline.html, driven in a real browser.

The reason this file exists: the page was unusable on a phone, and every
structural check in `test_render_md.py` passed while it was. Both faults were
in the arbitration between the browser and the script, which no amount of
reading the rendered HTML can see:

  * a tap aimed at a mark landed on `.lane-rule`, drawn over the lane's hit
    rect along the exact line the marks sit on, so the lane's handler never
    ran and the tooltip -- the only place the page says what an event was --
    could not be opened at all;

  * the taps that did reach a lane opened it and lost it in the same frame,
    because a pointer that cannot hover is destroyed when it is lifted, and
    the browser fires `pointerout` and `pointerleave` straight after the
    `pointerup` that ended it. The lane's `pointerleave` handler was written
    for a mouse leaving the lane, and hid the tooltip the tap had just asked
    for.

Neither reproduces with synthesised events: dispatching a `pointerup` by hand
is asserting the model of the browser that was wrong in the first place. So
touch here is real touch input, dispatched through CDP, and the browser
generates the whole pointer sequence itself.

Playwright is not a dependency of this repository and CI does not run this
file. Without it installed, or without a rendered page to open, it skips and
exits 0; nothing else in the project needs it. To run it:

    uv venv .venv && .venv/bin/python -m pip install playwright
    .venv/bin/python build/test_browser.py

Usage:
    python3 test_browser.py [path-to-timeline.html]
"""
import sys
from pathlib import Path

FAILURES = []


def check(name, ok, detail=''):
    print(f'{"pass" if ok else "FAIL"}  {name}' + (f'  {detail}' if detail else ''))
    if not ok:
        FAILURES.append(name)


# The chart holds a 56rem minimum width inside a container that scrolls, so on
# a phone most of any element's bounding box is off-screen and a point taken as
# a fraction of that box lands outside the window entirely. Every coordinate
# below is taken from the part of the box that is actually on screen.
POINT_IN = """
function pointIn(el, fx, fy) {
  const r = el.getBoundingClientRect();
  const left = Math.max(r.left, 4), right = Math.min(r.right, innerWidth - 4);
  const top = Math.max(r.top, 4), bot = Math.min(r.bottom, innerHeight - 4);
  return {x: left + (right - left) * fx, y: top + (bot - top) * fy,
          onScreen: right > left && bot > top};
}
"""

PHONE = {'viewport': {'width': 390, 'height': 844}, 'device_scale_factor': 3,
         'is_mobile': True, 'has_touch': True}


class Touch:
    """Real touch input, in the coordinates the page itself reports.

    CDP takes touch points in visual-viewport coordinates while the page reads
    client coordinates, and under mobile emulation the two differ by the visual
    viewport's offset -- here 26px, the difference between an 870px window and
    an 844px visual viewport. It is zero on a fresh load and 26 the moment
    anything scrolls, so it is read live rather than calibrated once.
    """

    def __init__(self, page):
        self.page = page
        self.cdp = page.context.new_cdp_session(page)

    def _send(self, kind, points):
        off = self.page.evaluate(
            '() => [visualViewport.offsetLeft, visualViewport.offsetTop]')
        self.cdp.send('Input.dispatchTouchEvent', {
            'type': kind,
            'touchPoints': [{'x': p[0] - off[0], 'y': p[1] - off[1], 'id': i}
                            for i, p in enumerate(points)],
        })

    def tap(self, x, y):
        self._send('touchStart', [(x, y)])
        self.page.wait_for_timeout(40)
        self._send('touchEnd', [])
        self.page.wait_for_timeout(120)

    def drag(self, x, y, dx, steps=6):
        """One finger, sideways: the gesture that scrolls the figure."""
        self._send('touchStart', [(x, y)])
        self.page.wait_for_timeout(30)
        for i in range(1, steps + 1):
            self._send('touchMove', [(x + dx * i / steps, y)])
            self.page.wait_for_timeout(30)
        self._send('touchEnd', [])
        self.page.wait_for_timeout(200)

    def pinch(self, cx, cy, start, end, steps=8):
        """Two fingers either side of cx, the gap between them start -> end."""
        def pts(gap):
            return [(cx - gap / 2, cy), (cx + gap / 2, cy)]
        self._send('touchStart', pts(start))
        self.page.wait_for_timeout(30)
        for i in range(1, steps + 1):
            self._send('touchMove', pts(start + (end - start) * i / steps))
            self.page.wait_for_timeout(30)
        self._send('touchEnd', [pts(end)[1]])
        self._send('touchEnd', [])
        self.page.wait_for_timeout(150)


def state(page):
    """Everything a check needs to know, read in one round trip."""
    return page.evaluate("""() => ({
      hidden: document.getElementById('tip').hidden,
      text: document.getElementById('tip').textContent.slice(0, 60),
      lit: document.querySelectorAll('.mark.on').length,
      frm: document.getElementById('from').value,
      to: document.getElementById('to').value,
      marks: [...document.querySelectorAll('.mark')]
               .filter(g => !g.hasAttribute('hidden')).length,
      scrollLeft: document.getElementById('figure').scrollLeft,
    })""")


def scroll_to(page, js_el):
    page.evaluate('() => { (' + js_el +
                  ").scrollIntoView({block: 'center', inline: 'center'}); }")
    page.wait_for_timeout(200)


def point_in(page, js_el, fx=0.5, fy=0.5):
    scroll_to(page, js_el)
    return page.evaluate('() => {' + POINT_IN + ' return pointIn(' + js_el +
                         f', {fx}, {fy}); }}')


def mark_at(track='ucl', nth=0):
    return ('[...document.querySelectorAll(\'.mark[data-track="%s"]\')]'
            '.filter(g => !g.hasAttribute("hidden"))[%d]' % (track, nth))


def lane_at(track='ucl'):
    return 'document.querySelector(\'.lane[data-lane="%s"]\')' % track


def day_under(page, client_x):
    """The day of the record currently drawn under a screen position.

    The property a pinch has to hold: whatever the fingers are on stays where
    they put it. Recomputed from the payload's geometry and the date boxes,
    which are the two things the page exposes.
    """
    return page.evaluate("""(cx) => {
      const D = JSON.parse(document.getElementById('payload').textContent);
      const svg = document.getElementById('chart');
      const pt = svg.createSVGPoint(); pt.x = cx; pt.y = 0;
      const x = pt.matrixTransform(svg.getScreenCTM().inverse()).x;
      const first = new Date(D.first + 'T00:00:00Z');
      const dayOf = iso =>
        Math.round((new Date(iso + 'T00:00:00Z') - first) / 86400000);
      const a = dayOf(document.getElementById('from').value);
      const b = dayOf(document.getElementById('to').value);
      return a + ((x - D.padL) / D.inner) * (b - a);
    }""", client_x)


def touch_run(browser, url):
    """A phone: nothing here has a hover, and one finger already means scroll."""
    print('\n--- touch, 390x844 ---')
    ctx = browser.new_context(**PHONE)
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('console',
            lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.goto(url)
    page.wait_for_timeout(400)
    check('the script runs with no errors', not errors, '; '.join(errors[:2]))

    # The declaration the pinch depends on. pan-x pan-y leaves one finger
    # scrolling the figure and the page, and takes only the two-finger zoom
    # away from the browser, which is the only way the script can be given it.
    check("the chart declines the browser's pinch and keeps one-finger pan",
          page.evaluate("""() => getComputedStyle(
            document.getElementById('chart')).touchAction""") == 'pan-x pan-y')

    # The fault that made every mark unreadable on a phone: the lane rule is
    # painted over the lane's hit rect, along the line the marks sit on.
    scroll_to(page, "document.getElementById('figure')")
    centres = page.evaluate('() => {' + POINT_IN + """
      return [...document.querySelectorAll('.lane')].map(l => {
        const p = pointIn(l, 0.5, 0.5);
        const at = document.elementFromPoint(p.x, p.y);
        return l.getAttribute('data-lane') + '->' +
          (at ? (at.getAttribute('data-lane') || at.getAttribute('class')) : 'null');
      }); }""")
    check('nothing drawn inside a lane can take a pointer from it',
          all(c.split('->')[0] == c.split('->')[1] for c in centres),
          str(centres))

    t = Touch(page)

    at = point_in(page, mark_at('ucl', 0))
    t.tap(at['x'], at['y'])
    first = state(page)
    check('tapping a mark opens the tooltip, and it stays open',
          not first['hidden'] and first['lit'] == 1, first['text'])

    at = point_in(page, mark_at('ucl', 40))
    t.tap(at['x'], at['y'])
    second = state(page)
    check('tapping another mark moves the tooltip to it',
          not second['hidden'] and second['lit'] == 1
          and second['text'] != first['text'], second['text'])

    # Touch never fires the pointerleave that puts it away for a mouse, so
    # tapping off the chart is the only way back.
    t.tap(20, 60)
    away = state(page)
    check('tapping away from the chart puts the tooltip down',
          away['hidden'] and away['lit'] == 0)

    at = point_in(page, "document.getElementById('plot-hit')", 0.5, 0.6)
    t.tap(at['x'], at['y'])
    reading = state(page)
    check('tapping the case panel reads out that week',
          not reading['hidden'] and 'Week to' in reading['text'],
          reading['text'])
    t.tap(20, 60)

    # One finger still belongs to the browser: the chart is two and a half
    # screens wide and this is how a reader crosses it.
    before = state(page)
    lane = point_in(page, lane_at('ucl'))
    t.drag(lane['x'] + 80, lane['y'], -160)
    panned = state(page)
    check('one finger still scrolls the chart sideways',
          panned['scrollLeft'] > before['scrollLeft'],
          f"scrollLeft {before['scrollLeft']:.0f} -> {panned['scrollLeft']:.0f}")
    check('and does not move the axis while doing it',
          panned['frm'] == before['frm'] and panned['to'] == before['to'],
          f"{panned['frm']}..{panned['to']}")

    # Two fingers: the gesture the page had no answer for.
    before = state(page)
    lane = point_in(page, lane_at('ucl'))
    cx = page.evaluate('() => innerWidth / 2')
    held = day_under(page, cx)
    t.pinch(cx, lane['y'], 60, 300)
    zoomed = state(page)
    check('a pinch apart narrows the time axis',
          zoomed['frm'] > before['frm'] or zoomed['to'] < before['to'],
          f"{before['frm']}..{before['to']} -> {zoomed['frm']}..{zoomed['to']}")
    check('and draws fewer marks, rather than the same ones spread out',
          zoomed['marks'] < before['marks'],
          f"{before['marks']} -> {zoomed['marks']}")
    # Within a day of where it was: the domain is rounded to whole days, and a
    # zoomed-in axis carries fewer days per pixel than the rounding.
    after_day = day_under(page, cx)
    check('the day between the fingers stays between them',
          abs(after_day - held) <= 2,
          f'day {held:.1f} -> {after_day:.1f} of the record')
    check('a pinch leaves no tooltip standing behind it', zoomed['hidden'])

    t.pinch(cx, lane['y'], 300, 40)
    t.pinch(cx, lane['y'], 300, 40)
    out = state(page)
    check('pinching together widens it back to the whole record',
          out['frm'] == before['frm'] and out['to'] == before['to'],
          f"{zoomed['frm']}..{zoomed['to']} -> {out['frm']}..{out['to']}")

    page.wait_for_timeout(500)
    at = point_in(page, mark_at('ucl', 0))
    t.tap(at['x'], at['y'])
    check('a tap after a pinch is still a tap', not state(page)['hidden'])

    # Double-click zooms out for a mouse; with the browser's own double-tap
    # zoom declined, the same handler answers a double tap.
    page.wait_for_timeout(500)
    lane = point_in(page, lane_at('ucl'))
    t.pinch(cx, lane['y'], 60, 300)
    narrowed = state(page)
    at = point_in(page, mark_at('ucl', 0))
    t.tap(at['x'], at['y'])
    t.tap(at['x'], at['y'])
    page.wait_for_timeout(200)
    reset = state(page)
    check('double tapping zooms back out, as double clicking does',
          reset['frm'] == before['frm'] and reset['to'] == before['to'],
          f"{narrowed['frm']}..{narrowed['to']} -> {reset['frm']}..{reset['to']}")

    check('no errors anywhere in the touch run', not errors,
          '; '.join(errors[:2]))
    ctx.close()


def mouse_run(browser, url):
    """A desktop: everything that worked before the touch paths were added."""
    print('\n--- mouse, 1280x900 ---')
    ctx = browser.new_context(viewport={'width': 1280, 'height': 900})
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(url)
    page.wait_for_timeout(300)

    at = point_in(page, mark_at('ucl', 0))
    page.mouse.move(at['x'], at['y'])
    page.wait_for_timeout(120)
    hovered = state(page)
    check('hovering a mark still opens the tooltip',
          not hovered['hidden'] and hovered['lit'] == 1, hovered['text'])

    page.mouse.move(at['x'], at['y'] - 200)
    page.wait_for_timeout(120)
    check('leaving the lane still puts it back down', state(page)['hidden'])

    # The same rule that swallowed taps was a hole in the hover path too, one
    # pixel wide and straight down the middle of every lane.
    lane = point_in(page, lane_at('ucl'))
    page.mouse.move(lane['x'], lane['y'])
    page.wait_for_timeout(120)
    check('hovering along the lane rule reaches the lane, not the rule',
          not state(page)['hidden'])

    before = state(page)
    page.mouse.move(lane['x'] - 200, lane['y'])
    page.mouse.down()
    for i in range(1, 6):
        page.mouse.move(lane['x'] - 200 + i * 40, lane['y'])
        page.wait_for_timeout(20)
    page.mouse.up()
    page.wait_for_timeout(200)
    dragged = state(page)
    check('drag to zoom still narrows the axis',
          dragged['frm'] > before['frm'] or dragged['to'] < before['to'],
          f"{before['frm']}..{before['to']} -> {dragged['frm']}..{dragged['to']}")

    page.mouse.dblclick(lane['x'], lane['y'])
    page.wait_for_timeout(200)
    back = state(page)
    check('double-click still zooms back out to the whole record',
          back['frm'] == before['frm'] and back['to'] == before['to'],
          f"{back['frm']}..{back['to']}")

    at = point_in(page, "document.getElementById('plot-hit')", 0.55, 0.6)
    page.mouse.move(at['x'], at['y'])
    page.wait_for_timeout(120)
    reading = state(page)
    check('the case crosshair still reads out a week',
          not reading['hidden'] and 'Week to' in reading['text'],
          reading['text'])
    page.mouse.move(5, 5)
    page.wait_for_timeout(120)
    check('and still goes away when the pointer leaves', state(page)['hidden'])

    page.evaluate("() => document.querySelector('.mark').focus()")
    page.wait_for_timeout(120)
    check('keyboard focus still shows what hover shows', not state(page)['hidden'])
    page.evaluate("() => document.querySelector('.mark').blur()")
    page.wait_for_timeout(120)
    check('and blur still takes it away', state(page)['hidden'])

    # The clamp that stops a typed range collapsing the chart to nothing.
    page.evaluate("""() => {
      const f = document.getElementById('from'), t = document.getElementById('to');
      f.value = '2020-06-01'; t.value = '2020-06-03';
      f.dispatchEvent(new Event('change', {bubbles: true}));
    }""")
    page.wait_for_timeout(150)
    narrow = state(page)
    check('a typed range narrower than a week is still refused',
          narrow['frm'] != '2020-06-01' or narrow['to'] != '2020-06-03',
          f"{narrow['frm']}..{narrow['to']}")

    check('no errors anywhere in the mouse run', not errors,
          '; '.join(errors[:2]))
    ctx.close()


def main():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('skip  browser checks (playwright is not installed)')
        return 0

    if len(sys.argv) > 1:
        page = Path(sys.argv[1]).resolve()
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import config
        cfg, _ = config.load(argv=[])
        page = cfg.path('paths.html_out')
    if not page.exists():
        print(f'skip  browser checks (nothing rendered at {page})')
        return 0
    url = page.as_uri()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            touch_run(browser, url)
            mouse_run(browser, url)
            browser.close()
    except Exception as exc:                       # noqa: BLE001
        # A browser that will not start is not a failing page. Say which it is
        # rather than reporting a fault in the thing under test.
        print(f'skip  browser checks (could not drive a browser: {exc})')
        return 0

    print()
    if FAILURES:
        print(f'{len(FAILURES)} check(s) failed: {FAILURES}')
        return 1
    print('all checks passed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
