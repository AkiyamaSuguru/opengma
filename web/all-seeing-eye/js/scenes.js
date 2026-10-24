/* 全知之眼 · 各幕插画（1600×1000 的 SVG 画布，二维日漫风格） */
(function () {
  'use strict';

  // ---------- 小工具 ----------

  function rng(seed) {
    return function () {
      seed |= 0; seed = seed + 0x6D2B79F5 | 0;
      let t = Math.imul(seed ^ seed >>> 15, 1 | seed);
      t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t;
      return ((t ^ t >>> 14) >>> 0) / 4294967296;
    };
  }
  const f = (n) => (+n).toFixed(1);

  function stars(r, n, x0, y0, w, h, maxR, color) {
    let s = '';
    for (let i = 0; i < n; i++) {
      const x = x0 + r() * w, y = y0 + r() * h;
      const rad = Math.pow(r(), 3) * (maxR || 1.8) + 0.35;
      const tw = r() < 0.35;
      const st = tw ? ` class="tw" style="animation-delay:${f(-r() * 4)}s;animation-duration:${f(2 + r() * 3)}s"` : '';
      s += `<circle cx="${f(x)}" cy="${f(y)}" r="${rad.toFixed(2)}" fill="${color || '#fff'}" opacity="${(0.35 + r() * 0.65).toFixed(2)}"${st}/>`;
    }
    return s;
  }

  function sparkle(x, y, s, fill, extra) {
    x = +x; y = +y; s = +(+s).toFixed(1);
    return `<path ${extra || ''} d="M${x} ${y - s}Q${x} ${y} ${x + s} ${y}Q${x} ${y} ${x} ${y + s}Q${x} ${y} ${x - s} ${y}Q${x} ${y} ${x} ${y - s}Z" fill="${fill}"/>`;
  }

  function skyline(r, x0, x1, base, minH, maxH, fill, win, wp) {
    let s = '', x = x0;
    while (x < x1) {
      const w = 34 + r() * 70, h = minH + r() * (maxH - minH);
      s += `<rect x="${f(x)}" y="${f(base - h)}" width="${f(w)}" height="${f(h + 4)}" fill="${fill}"/>`;
      if (win) {
        for (let wy = base - h + 12; wy < base - 10; wy += 17) {
          for (let wx = x + 7; wx < x + w - 9; wx += 13) {
            if (r() < wp) s += `<rect x="${f(wx)}" y="${f(wy)}" width="5" height="8" fill="${win}" opacity="${(0.4 + r() * 0.6).toFixed(2)}"/>`;
          }
        }
      }
      if (r() < 0.22) s += `<rect x="${f(x + w / 2 - 1.5)}" y="${f(base - h - 34)}" width="3" height="36" fill="${fill}"/>`;
      x += w + r() * 5;
    }
    return s;
  }

  // 赛璐璐风格的云：阴影层 + 主体 + 高光
  function cloud(x, y, s, c1, c2, c3) {
    const b = [[0, 0, 60], [58, -24, 52], [118, 2, 58], [-52, 12, 46], [168, 18, 42], [62, 26, 50]];
    let sh = '', ba = '', hi = '';
    for (const [a, bb, rr] of b) {
      sh += `<circle cx="${a + 6}" cy="${bb + 16}" r="${rr}"/>`;
      ba += `<circle cx="${a}" cy="${bb}" r="${rr}"/>`;
      hi += `<circle cx="${a - 10}" cy="${bb - 12}" r="${rr * 0.62}"/>`;
    }
    return `<g transform="translate(${x} ${y}) scale(${s})"><g fill="${c2}">${sh}</g><g fill="${c1}">${ba}</g><g fill="${c3}" opacity=".75">${hi}</g></g>`;
  }

  function person(x, y, h, fill, attrs) {
    const hr = h * 0.13;
    return `<g fill="${fill}" ${attrs || ''}><circle cx="${f(x)}" cy="${f(y - h + hr)}" r="${f(hr)}"/>` +
      `<path d="M${f(x - h * 0.17)} ${f(y)}L${f(x - h * 0.16)} ${f(y - h + hr * 2.5)}Q${f(x)} ${f(y - h + hr * 1.9)} ${f(x + h * 0.16)} ${f(y - h + hr * 2.5)}L${f(x + h * 0.17)} ${f(y)}Z"/></g>`;
  }

  // 墙上的钟：时间的隐喻，秒针一直在走
  function clock(x, y, r, face, ink, h, m) {
    const ha = (h % 12 + m / 60) * 30, ma = m * 6;
    let ticks = '';
    for (let i = 0; i < 12; i++) {
      const a = i * Math.PI / 6;
      ticks += `<line x1="${f(x + Math.sin(a) * r * 0.78)}" y1="${f(y - Math.cos(a) * r * 0.78)}" x2="${f(x + Math.sin(a) * r * 0.9)}" y2="${f(y - Math.cos(a) * r * 0.9)}"/>`;
    }
    return `<g><circle cx="${x}" cy="${y}" r="${r + 5}" fill="${ink}"/><circle cx="${x}" cy="${y}" r="${r}" fill="${face}"/>` +
      `<g stroke="${ink}" stroke-width="3">${ticks}</g>` +
      `<line x1="${x}" y1="${y}" x2="${x}" y2="${y - r * 0.5}" stroke="${ink}" stroke-width="5" stroke-linecap="round" transform="rotate(${ha} ${x} ${y})"/>` +
      `<line x1="${x}" y1="${y}" x2="${x}" y2="${y - r * 0.75}" stroke="${ink}" stroke-width="3" stroke-linecap="round" transform="rotate(${ma} ${x} ${y})"/>` +
      `<line class="sec-hand" style="transform-origin:${x}px ${y}px" x1="${x}" y1="${y + r * 0.15}" x2="${x}" y2="${y - r * 0.82}" stroke="#b3161f" stroke-width="1.6"/>` +
      `<circle cx="${x}" cy="${y}" r="4" fill="#b3161f"/></g>`;
  }

  // 藏在云里的“天之眼”轮廓
  function skyEye(cx, cy, w, h, stroke, iris, op) {
    return `<g opacity="${op}"><path d="M${cx - w} ${cy}Q${cx} ${cy - h * 2} ${cx + w} ${cy}Q${cx} ${cy + h * 1.6} ${cx - w} ${cy}Z" fill="none" stroke="${stroke}" stroke-width="2.5"/>` +
      `<circle cx="${cx}" cy="${cy}" r="${h * 0.62}" fill="${iris}"/><ellipse cx="${cx}" cy="${cy}" rx="${h * 0.12}" ry="${h * 0.45}" fill="#000"/></g>`;
  }

  // ---------- 序幕 · 睁眼 ----------
  function prologue() {
    const r = rng(7);
    let runes = '';
    const glyphs = 'ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ';
    for (let i = 0; i < 48; i++) {
      const a = i / 48 * Math.PI * 2;
      runes += `<text x="${f(800 + Math.cos(a) * 330)}" y="${f(500 + Math.sin(a) * 330)}" transform="rotate(${f(a * 180 / Math.PI + 90)} ${f(800 + Math.cos(a) * 330)} ${f(500 + Math.sin(a) * 330)})" text-anchor="middle" dominant-baseline="middle">${glyphs[i % glyphs.length]}</text>`;
    }
    let dust = '';
    for (let i = 0; i < 160; i++) {
      const t = r();
      const up = r() < 0.5;
      // 沿着眼睑曲线撒星尘
      const x = 440 + t * 720;
      const y0 = up ? 500 - Math.sin(t * Math.PI) * 230 * 0.75 : 500 + Math.sin(t * Math.PI) * 185 * 0.75;
      const y = y0 + (r() - 0.5) * 22;
      dust += `<circle cx="${f(x)}" cy="${f(y)}" r="${(0.6 + r() * 2.2).toFixed(2)}" fill="${r() < 0.3 ? '#ffcf7a' : '#f6e6c8'}" class="tw" style="animation-delay:${f(-r() * 3)}s"/>`;
    }
    return `<svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<defs>
  <radialGradient id="p0bg" cx=".5" cy=".5" r=".75"><stop offset="0" stop-color="#2a0718"/><stop offset=".5" stop-color="#12030f"/><stop offset="1" stop-color="#030006"/></radialGradient>
  <filter id="p0blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="46"/></filter>
  <filter id="p0glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="8" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <radialGradient id="p0iris"><stop offset="0" stop-color="#fff6d0"/><stop offset=".22" stop-color="#ffb02e"/><stop offset=".6" stop-color="#b3200f"/><stop offset=".92" stop-color="#3a0208"/><stop offset="1" stop-color="#3a0208" stop-opacity="0"/></radialGradient>
</defs>
<rect width="1600" height="1000" fill="url(#p0bg)"/>
<g filter="url(#p0blur)" opacity=".85">
  <ellipse cx="420" cy="330" rx="330" ry="140" fill="#5a0c3a"/>
  <ellipse cx="1200" cy="660" rx="400" ry="170" fill="#36094d"/>
  <ellipse cx="820" cy="500" rx="300" ry="100" fill="#7a1a1a"/>
  <ellipse cx="1250" cy="230" rx="200" ry="80" fill="#1a1a5a"/>
</g>
${stars(r, 340, 0, 0, 1600, 1000, 2.2)}
<g class="spin-slow" style="transform-origin:800px 500px;animation:spin 120s linear infinite">
  <g fill="#c9a45c" opacity=".55" font-family="Noto Sans Runic, serif" font-size="22">${runes}</g>
</g>
<g fill="none" stroke="#c9a45c" opacity=".35">
  <circle cx="800" cy="500" r="300" stroke-dasharray="2 12"/>
  <circle cx="800" cy="500" r="360"/>
  <circle cx="800" cy="500" r="420" stroke-dasharray="40 8 4 8"/>
  <path d="M800 80L1164 710L436 710Z" stroke-width="1.5"/>
  <path d="M800 920L436 290L1164 290Z" stroke-width="1" opacity=".6"/>
</g>
<g filter="url(#p0glow)">${dust}</g>
<g class="cosmos-iris" style="transition:transform 3.5s cubic-bezier(.2,.8,.2,1)">
  <circle cx="800" cy="500" r="140" fill="url(#p0iris)"/>
  <ellipse cx="800" cy="500" rx="16" ry="96" fill="#050002"/>
  <ellipse cx="760" cy="455" rx="22" ry="12" fill="#fff" opacity=".7"/>
</g>
${sparkle(800, 500, 40, '#fff', 'class="tw" opacity=".9"')}
</svg>`;
  }

  // ---------- 第一幕 · 降生（2041，雨夜的产房） ----------
  function birth() {
    const r = rng(11);
    let rain = '';
    for (let i = 0; i < 130; i++) {
      const x = 900 + r() * 620, y = r() * 1000, l = 22 + r() * 34;
      rain += `<line x1="${f(x)}" y1="${f(y)}" x2="${f(x - 3)}" y2="${f(y + l)}"/><line x1="${f(x)}" y1="${f(y - 1000)}" x2="${f(x - 3)}" y2="${f(y - 1000 + l)}"/>`;
    }
    let bokeh = '';
    for (let i = 0; i < 26; i++) {
      bokeh += `<circle cx="${f(930 + r() * 500)}" cy="${f(470 + r() * 210)}" r="${f(6 + r() * 16)}" fill="${['#ffb86b', '#ff7aa8', '#ffe39a', '#8fd0ff'][i % 4]}" opacity="${(0.15 + r() * 0.35).toFixed(2)}"/>`;
    }
    const ecg = 'M0 30 L40 30 L50 30 L56 14 L62 46 L68 4 L74 52 L80 30 L120 30 L130 30 L136 14 L142 46 L148 4 L154 52 L160 30 L200 30';
    return `<svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<defs>
  <linearGradient id="p1wall" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#3a2228"/><stop offset=".45" stop-color="#22141f"/><stop offset="1" stop-color="#151223"/></linearGradient>
  <linearGradient id="p1sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#070b1f"/><stop offset=".55" stop-color="#1b2550"/><stop offset="1" stop-color="#40305e"/></linearGradient>
  <radialGradient id="p1lamp" cx="0" cy="0" r="1" gradientUnits="userSpaceOnUse" gradientTransform="translate(250 330) scale(620)"><stop offset="0" stop-color="#ffcf8a" stop-opacity=".75"/><stop offset=".35" stop-color="#ff9a5a" stop-opacity=".25"/><stop offset="1" stop-color="#ff9a5a" stop-opacity="0"/></radialGradient>
  <linearGradient id="p1gown" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#d9c2b4"/><stop offset=".6" stop-color="#9fb0d6"/><stop offset="1" stop-color="#7d8fc0"/></linearGradient>
  <linearGradient id="p1curtain" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#2a1426"/><stop offset=".5" stop-color="#4c2546"/><stop offset="1" stop-color="#2a1426"/></linearGradient>
  <filter id="p1blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter>
  <filter id="p1blur2" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="22"/></filter>
  <clipPath id="p1win"><rect x="920" y="110" width="520" height="570" rx="6"/></clipPath>
</defs>
<rect width="1600" height="1000" fill="url(#p1wall)"/>
<rect y="820" width="1600" height="180" fill="#120a14"/>
<rect y="815" width="1600" height="8" fill="#2e1a26"/>
<!-- 窗外：雨夜的海港城 -->
<g clip-path="url(#p1win)">
  <rect x="900" y="100" width="560" height="600" fill="url(#p1sky)"/>
  <circle cx="1330" cy="215" r="50" fill="#f4ecd8" filter="url(#p1blur)" opacity=".85"/>
  <g filter="url(#p1blur)" opacity=".9">
    ${cloud(1060, 240, 1.1, '#2c2f55', '#1a1c3a', '#4a4a78')}
    ${cloud(1300, 290, 0.9, '#2c2f55', '#1a1c3a', '#4a4a78')}
  </g>
  ${skyEye(1170, 300, 120, 26, '#ff5a4a', '#8a1010', 0.2)}
  ${skyline(rng(3), 900, 1460, 690, 140, 340, '#2c2648', null, 0)}
  ${skyline(rng(4), 900, 1460, 690, 60, 250, '#120f24', '#ffcc7a', 0.22)}
  <g filter="url(#p1blur)">${bokeh}</g>
  <g class="rain" stroke="#b9c8ff" stroke-width="1.4" opacity=".45">${rain}</g>
  <path d="M920 110L1080 110L940 680L920 680Z" fill="#fff" opacity=".04"/>
  <path d="M1150 110L1210 110L1040 680L990 680Z" fill="#fff" opacity=".035"/>
</g>
<g fill="none" stroke="#1a1018" stroke-width="18">
  <rect x="920" y="110" width="520" height="570" rx="6"/>
  <line x1="1180" y1="110" x2="1180" y2="680"/>
  <line x1="920" y1="400" x2="1440" y2="400"/>
</g>
<rect x="905" y="676" width="550" height="16" fill="#2b1b26"/>
<!-- 窗帘 -->
<path d="M860 80 C 900 300 870 520 900 780 L 960 780 C 940 520 960 300 950 80 Z" fill="url(#p1curtain)"/>
<path d="M1450 80 C 1470 300 1440 520 1470 780 L 1530 780 C 1520 520 1540 300 1520 80 Z" fill="url(#p1curtain)"/>
<rect x="840" y="72" width="720" height="14" rx="7" fill="#100810"/>
<!-- 窗光落在地面 -->
<path d="M920 690 L1440 690 L1260 1000 L560 1000 Z" fill="#9ec3ff" opacity=".07"/>
<!-- 墙上的钟：凌晨两点四十一分 -->
${clock(420, 190, 54, '#e9dccb', '#2a1820', 2, 41)}
<!-- 台灯与暖光 -->
<rect width="1600" height="1000" fill="url(#p1lamp)"/>
<path d="M200 300 L300 300 L280 250 L220 250 Z" fill="#e7b77a"/>
<rect x="246" y="300" width="8" height="140" fill="#3a2420"/>
<rect x="200" y="440" width="100" height="16" rx="4" fill="#3a2420"/>
<rect x="170" y="456" width="160" height="364" fill="#2a1820"/>
<rect x="170" y="456" width="160" height="10" fill="#4a2c2c"/>
<!-- 生命监护仪（挂在墙上） -->
<g transform="translate(640 120) scale(.82)">
  <rect x="-10" y="-10" width="250" height="130" rx="10" fill="#0c0f14"/>
  <rect x="0" y="0" width="230" height="110" rx="4" fill="#06110c"/>
  <path class="ecg" d="${ecg}" transform="translate(14 30)" fill="none" stroke="#5dff9a" stroke-width="2.5"/>
  <text x="200" y="100" fill="#5dff9a" font-family="monospace" font-size="18" text-anchor="end">♥ 128</text>
  <rect x="100" y="-60" width="30" height="50" fill="#0c0f14"/>
</g>
<!-- 病床 -->
<path d="M240 640 L940 640 L960 760 L220 760 Z" fill="#cfc6d8"/>
<path d="M240 640 L940 640 L944 662 L236 662 Z" fill="#eee8f2"/>
<path d="M220 760 L960 760 L960 800 L220 800 Z" fill="#8f86a8"/>
<rect x="232" y="800" width="14" height="40" fill="#2a2030"/><rect x="934" y="800" width="14" height="40" fill="#2a2030"/>
<path d="M600 640 C 700 610 820 620 940 640 L960 760 L640 760 Z" fill="#b8b2d0" opacity=".7"/>
<path d="M300 610 C 300 570 420 560 470 600 L470 650 L300 650 Z" fill="#f2eef6"/>
<!-- 母亲（侧坐，望向怀中的婴儿） -->
<g>
  <path d="M552 330 C 498 340 488 430 496 520 C 502 580 514 620 530 650 L 600 650 C 585 600 575 540 582 470 Z" fill="#2a1830"/>
  <path d="M530 650 C 528 560 545 495 586 470 C 618 452 652 462 668 494 C 684 530 694 600 704 650 Z" fill="url(#p1gown)"/>
  <path d="M668 494 C 684 530 694 600 704 650" fill="none" stroke="#bcd4ff" stroke-width="3" opacity=".8"/>
  <path d="M600 438 L 628 438 L 632 474 L 604 476 Z" fill="#e8bfae"/>
  <ellipse cx="598" cy="372" rx="58" ry="56" fill="#2a1830"/>
  <path d="M582 352 C 600 336 642 342 652 372 C 656 386 659 398 664 410 L 653 414 C 656 426 650 442 640 450 C 624 460 600 456 588 440 C 572 420 568 380 582 352 Z" fill="#f4d5c4"/>
  <path d="M664 410 L 653 414 C 656 426 650 442 640 450" fill="none" stroke="#bcd4ff" stroke-width="2.5" opacity=".9"/>
  <path d="M548 360 C 560 318 628 306 658 352 C 642 346 634 356 626 372 C 618 356 604 352 594 368 C 590 356 578 352 568 372 C 560 392 556 420 560 460 C 540 430 538 392 548 360 Z" fill="#3a2440"/>
  <path d="M572 330 C 596 318 626 320 640 330" fill="none" stroke="#7a5a8a" stroke-width="4" opacity=".7"/>
  <path d="M616 400 Q 630 409 643 399" fill="none" stroke="#3a2030" stroke-width="3.2" stroke-linecap="round"/>
  <path d="M641 399 L 648 395" stroke="#3a2030" stroke-width="2.4" stroke-linecap="round"/>
  <ellipse cx="640" cy="424" rx="10" ry="4.5" fill="#ff8a9a" opacity=".5"/>
  <path d="M646 438 Q 652 440 656 436" fill="none" stroke="#a0505a" stroke-width="2" stroke-linecap="round"/>
  <!-- 手臂与襁褓 -->
  <path d="M640 500 C 670 520 690 560 700 590 L 730 586 C 720 548 700 506 664 486 Z" fill="#a9b8dc"/>
  <ellipse cx="712" cy="568" rx="78" ry="48" transform="rotate(-14 712 568)" fill="#f3eef6"/>
  <path d="M650 580 C 690 600 740 596 780 560" fill="none" stroke="#c8bedc" stroke-width="3"/>
  <path d="M670 540 C 700 556 740 552 770 532" fill="none" stroke="#d8d0e6" stroke-width="2.5"/>
  <circle cx="742" cy="536" r="25" fill="#f8d8c8"/>
  <path d="M724 522 C 732 508 752 506 762 518" fill="none" stroke="#6a4a5a" stroke-width="3" stroke-linecap="round"/>
  <ellipse cx="752" cy="536" rx="3.6" ry="4.6" fill="#1a1020"/><circle cx="753" cy="534.5" r="1.3" fill="#fff"/>
  <ellipse cx="738" cy="536" rx="3.2" ry="4.2" fill="#1a1020"/><circle cx="739" cy="534.5" r="1.2" fill="#fff"/>
  <ellipse cx="756" cy="546" rx="5" ry="2.5" fill="#ff8a9a" opacity=".55"/>
  <path d="M640 590 C 680 600 720 598 740 588 L 744 604 C 700 618 660 612 636 604 Z" fill="#e8bfae"/>
  <path d="M766 520 C 772 530 772 544 764 556" fill="none" stroke="#bcd4ff" stroke-width="2.5" opacity=".9"/>
</g>
<!-- 婴儿视线所及：一缕从窗外射入的冷光 -->
<path d="M760 536 L 1180 300" stroke="#ffdca0" stroke-width="1.2" stroke-dasharray="3 10" opacity=".35"/>
</svg>`;
  }

  // ---------- 第二幕 · 好奇（2048，屋顶的纸筒望远镜） ----------
  function curiosity() {
    const r = rng(21);
    let fireflies = '';
    for (let i = 0; i < 14; i++) {
      fireflies += `<circle class="firefly" cx="${f(200 + r() * 1200)}" cy="${f(700 + r() * 250)}" r="${f(2 + r() * 2.5)}" fill="#ffe9a0" style="animation-delay:${f(-r() * 5)}s;animation-duration:${f(4 + r() * 3)}s"/>`;
    }
    let sparkles = '';
    for (let i = 0; i < 14; i++) sparkles += sparkle(f(80 + r() * 1440), f(40 + r() * 420), 5 + r() * 9, '#fff', `class="tw" style="animation-delay:${f(-r() * 3)}s"`);
    return `<svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<defs>
  <linearGradient id="p2sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#040820"/><stop offset=".38" stop-color="#16206a"/><stop offset=".62" stop-color="#4b2f86"/><stop offset=".76" stop-color="#c0607a"/><stop offset=".84" stop-color="#f6a27a"/></linearGradient>
  <linearGradient id="p2shoot" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff"/></linearGradient>
  <filter id="p2blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="30"/></filter>
  <filter id="p2glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
  <linearGradient id="p2tube" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#d9a368"/><stop offset="1" stop-color="#8a5a2e"/></linearGradient>
</defs>
<rect width="1600" height="1000" fill="url(#p2sky)"/>
<!-- 银河 -->
<g transform="rotate(-24 800 300)">
  <ellipse cx="800" cy="300" rx="900" ry="80" fill="#c8b6ff" opacity=".22" filter="url(#p2blur)"/>
  <ellipse cx="800" cy="300" rx="760" ry="34" fill="#ffd6f0" opacity=".2" filter="url(#p2blur)"/>
  <g>${stars(r, 260, -100, 230, 1800, 140, 1.4)}</g>
</g>
${stars(r, 240, 0, 0, 1600, 640, 2)}
<g filter="url(#p2glow)">${sparkles}</g>
<g class="shoot" style="transform-box:view-box"><line x1="1380" y1="90" x2="1560" y2="10" stroke="url(#p2shoot)" stroke-width="3" stroke-linecap="round" transform="rotate(180 1380 90)"/><circle cx="1380" cy="90" r="3" fill="#fff"/></g>
<!-- 远处的城市 -->
${skyline(rng(5), -20, 1620, 790, 80, 230, '#3a2a62', null, 0)}
${skyline(rng(6), -20, 1620, 800, 40, 160, '#1c1440', '#ffd27a', 0.18)}
<!-- 屋顶 -->
<rect y="798" width="1600" height="30" fill="#2a1f48"/>
<rect y="798" width="1600" height="4" fill="#f0a0a0" opacity=".45"/>
<rect y="828" width="1600" height="172" fill="#140e2a"/>
<g stroke="#241a40" stroke-width="2">${Array.from({ length: 16 }, (_, i) => `<line x1="${i * 100}" y1="828" x2="${i * 100 - 60}" y2="1000"/>`).join('')}</g>
<!-- 水塔 -->
<g fill="#120c26">
  <rect x="1280" y="520" width="190" height="200" rx="8"/>
  <ellipse cx="1375" cy="520" rx="95" ry="22"/>
  <path d="M1280 520 L1375 460 L1470 520 Z"/>
  <rect x="1295" y="720" width="12" height="80"/><rect x="1443" y="720" width="12" height="80"/><rect x="1368" y="720" width="12" height="80"/>
  <rect x="1500" y="380" width="5" height="420"/>
  <path d="M1470 400 L1540 400 M1480 430 L1530 430" stroke="#120c26" stroke-width="4"/>
</g>
<rect x="1460" y="520" width="10" height="200" fill="#e8909a" opacity=".35"/>
<circle class="blinkred" cx="1502" cy="378" r="6" fill="#ff3030"/>
<!-- 晾衣绳 -->
<g>
  <rect x="140" y="560" width="8" height="240" fill="#100a22"/><rect x="600" y="560" width="8" height="240" fill="#100a22"/>
  <path d="M144 570 Q 374 620 604 570" fill="none" stroke="#0c0820" stroke-width="2"/>
  <path class="flutter" d="M190 586 L 290 600 L 292 720 Q 260 730 240 722 Q 210 712 192 724 Z" fill="#e8e0f8"/>
  <path d="M250 596 L 260 722" stroke="#b8a8e0" stroke-width="2" opacity=".7"/>
  <path class="flutter" style="animation-delay:-1s" d="M330 605 L 430 606 L 432 690 Q 400 700 380 692 Q 350 684 332 696 Z" fill="#f4c8d8"/>
  <path class="flutter" style="animation-delay:-.4s" d="M470 600 L 540 590 L 544 660 Q 520 670 500 664 L 472 668 Z" fill="#c8d8f8"/>
</g>
<!-- 女孩（七岁），坐在护栏上举起纸筒望远镜 -->
<g>
  <path d="M770 802 C 764 742 774 702 800 686 C 822 676 852 678 866 690 C 886 706 892 752 886 802 Z" fill="#2e2558"/>
  <path d="M866 690 C 886 706 892 752 886 802" fill="none" stroke="#ffb0a0" stroke-width="3" opacity=".8"/>
  <ellipse cx="826" cy="690" rx="40" ry="15" fill="#3a3070"/>
  <g transform="translate(790 672) rotate(-148)">
    <rect x="-4" y="-13" width="170" height="26" rx="4" fill="url(#p2tube)"/>
    <rect x="40" y="-14" width="10" height="28" fill="#f2f0e8" opacity=".8"/>
    <rect x="100" y="-14" width="10" height="28" fill="#f2f0e8" opacity=".8"/>
    <rect x="150" y="-17" width="30" height="34" rx="5" fill="#6a4020"/>
    <ellipse cx="180" cy="0" rx="4" ry="15" fill="#9fd8ff" opacity=".9"/>
  </g>
  ${sparkle(640, 586, 16, '#fff', 'class="tw"')}
  <path d="M800 700 C 786 690 776 680 770 668" stroke="#2e2558" stroke-width="22" stroke-linecap="round" fill="none"/>
  <path d="M852 698 C 842 684 820 676 800 670" stroke="#3a3070" stroke-width="20" stroke-linecap="round" fill="none"/>
  <circle cx="772" cy="666" r="10" fill="#f0c8b8"/>
  <circle cx="826" cy="640" r="38" fill="#1c1530"/>
  <path d="M792 646 C 784 606 816 594 836 598 C 862 604 870 630 862 660 L 858 676 L 849 664 L 841 680 L 832 667 L 822 682 L 814 667 L 804 678 L 800 664 Z" fill="#241a40"/>
  <path d="M836 600 C 830 582 842 572 854 578 C 846 582 840 590 838 602 Z" fill="#241a40"/>
  <path d="M860 618 C 866 634 866 652 860 672" fill="none" stroke="#ffb0a0" stroke-width="3" opacity=".75"/>
  <path d="M796 616 C 806 604 822 600 834 602" fill="none" stroke="#6a5aa8" stroke-width="3" opacity=".6"/>
</g>
<!-- 一只陪着她的猫 -->
<g fill="#100a22">
  <ellipse cx="955" cy="786" rx="26" ry="20"/>
  <circle cx="950" cy="756" r="16"/>
  <path d="M938 748 L 940 730 L 950 744 Z M 956 744 L 964 730 L 964 750 Z"/>
  <path d="M980 796 C 1010 790 1010 760 996 750" fill="none" stroke="#100a22" stroke-width="6" stroke-linecap="round"/>
</g>
<path d="M964 742 C 968 750 968 760 964 768" fill="none" stroke="#ffb0a0" stroke-width="2" opacity=".6"/>
<g filter="url(#p2glow)">${fireflies}</g>
</svg>`;
  }

  // ---------- 第三幕 · 阶梯（2057，被编号的城市） ----------
  function ladder() {
    const r = rng(31);
    let tiers = '';
    for (let i = 5; i >= 0; i--) {
      const y = 880 - i * 132, w = 1560 - i * 240, x0 = 800 - w / 2;
      const shade = [0x55, 0x60, 0x6c, 0x7a, 0x8a, 0x9c][i];
      const c = `rgb(${shade - 6},${shade - 10},${shade + 4})`;
      const top = `rgb(${shade + 28},${shade + 22},${shade + 34})`;
      tiers += skyline(rng(40 + i), x0 + 20, x0 + w - 20, y - 6, 20, 90 - i * 10, c, i < 3 ? '#e8d8a0' : null, 0.05);
      tiers += `<path d="M${x0} ${y} L${x0 + w} ${y} L${x0 + w - 30} ${y + 34} L${x0 + 30} ${y + 34} Z" fill="${c}"/>`;
      tiers += `<rect x="${x0}" y="${y - 6}" width="${w}" height="8" fill="${top}"/>`;
      // 人群：灰色、相同、各自带着编号
      const n = 14 - i * 2, h = 46 - i * 6;
      for (let k = 0; k < n; k++) {
        const px = x0 + 40 + r() * (w - 80);
        tiers += person(px, y - 4, h, `rgb(${shade - 20},${shade - 22},${shade - 14})`);
        if (r() < 0.45) tiers += `<text x="${f(px)}" y="${f(y - h - 10)}" font-family="monospace" font-size="${12 - i}" fill="#c63a3a" opacity=".85" text-anchor="middle">${String(Math.floor(r() * 9000) + 1000)}</text>`;
      }
      // 通往上一层的台阶
      if (i < 5) {
        const sx = 800 + (i % 2 ? -1 : 1) * (w / 2 - 260 + i * 30);
        const steps = 7;
        for (let s = 0; s < steps; s++) {
          tiers += `<rect x="${f(sx - 50 + (i % 2 ? s * 12 : -s * 12))}" y="${f(y - 6 - (s + 1) * 18.8)}" width="100" height="19" fill="${top}" stroke="${c}" stroke-width="2"/>`;
        }
      }
    }
    const tags = [
      [140, 160, 'No.2041-0417 / 天野 遥'], [1180, 120, '评级 B+  ▲ 0.3'], [120, 520, '阶层：第 6 层 / 共 9 层'],
      [1240, 460, '排名 3,882 / 120,000'], [560, 70, '■ 监视中 ■'], [180, 300, '社会信用 712'], [1330, 280, '流动许可：未发放']
    ];
    const tagSvg = tags.map(([x, y, t], k) => `<text class="tw" style="animation-delay:${-k * 0.7}s" x="${x}" y="${y}" font-family="monospace" font-size="20" fill="#d23a3a" opacity=".8">${t}</text>`).join('');
    return `<svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<defs>
  <linearGradient id="p3sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e2d8de"/><stop offset=".3" stop-color="#9a8e9e"/><stop offset=".75" stop-color="#4d4456"/><stop offset="1" stop-color="#241e2a"/></linearGradient>
  <linearGradient id="p3beam" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ff4a3a" stop-opacity=".55"/><stop offset="1" stop-color="#ff4a3a" stop-opacity="0"/></linearGradient>
  <linearGradient id="p3ray" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <radialGradient id="p3star"><stop offset="0" stop-color="#e8f4ff"/><stop offset=".2" stop-color="#7ec8ff" stop-opacity=".8"/><stop offset="1" stop-color="#2a6aff" stop-opacity="0"/></radialGradient>
  <filter id="p3blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="18"/></filter>
</defs>
<rect width="1600" height="1000" fill="url(#p3sky)"/>
<g fill="url(#p3ray)">
  <path d="M800 -60 L 520 1000 L 600 1000 Z"/><path d="M800 -60 L 900 1000 L 1020 1000 Z"/>
  <path d="M800 -60 L 200 1000 L 260 1000 Z"/><path d="M800 -60 L 1260 1000 L 1400 1000 Z"/>
</g>
<g filter="url(#p3blur)" opacity=".6">
  ${cloud(80, 120, 1.6, '#cfc4cf', '#9a8ea0', '#f2eaf0')}
  ${cloud(1180, 90, 1.5, '#cfc4cf', '#9a8ea0', '#f2eaf0')}
</g>
${tiers}
<!-- 凝视的光束：横扫人群 -->
<path class="sweep" style="transform-origin:800px -40px" d="M800 -40 L 690 1000 L 910 1000 Z" fill="url(#p3beam)"/>
<!-- 一个坠落的人 -->
<g transform="translate(330 470) rotate(150)">${person(0, 0, 34, '#5a5260')}</g>
<g stroke="#5a5260" stroke-width="2" opacity=".6"><line x1="318" y1="400" x2="318" y2="440"/><line x1="340" y1="396" x2="340" y2="430"/></g>
${tagSvg}
<!-- 云缝里，一颗唯一有颜色的星 -->
<circle cx="1390" cy="380" r="90" fill="url(#p3star)" class="pulse"/>
${sparkle(1390, 380, 30, '#fff', 'class="tw"')}
<!-- 前景台阶 -->
<path d="M980 1000 L 980 940 L 1080 940 L 1080 900 L 1180 900 L 1180 960 L 1600 960 L 1600 1000 Z" fill="#1a1520"/>
<path d="M980 940 L 1080 940 M1080 900 L 1180 900" stroke="#6a6070" stroke-width="3"/>
<!-- 遥（十六岁）：站在台阶上，没有看阶梯，而是望向那颗星 -->
<g>
  <path d="M1170 698 C 1130 700 1096 720 1066 744 C 1102 728 1128 724 1158 716 Z" fill="#141018"/>
  <path d="M1164 900 L 1160 830 L 1176 830 L 1178 900 Z M 1196 900 L 1194 830 L 1210 830 L 1212 900 Z" fill="#1d1a28"/>
  <path d="M1156 902 L 1182 902 L 1182 912 L 1150 912 Z M 1192 902 L 1218 902 L 1220 912 L 1190 912 Z" fill="#0c0a10"/>
  <path d="M1138 836 L 1232 836 L 1222 776 L 1146 776 Z" fill="#1f2747"/>
  <path d="M1160 780 L 1154 836 M1180 780 L 1178 836 M1200 780 L 1202 836 M1218 780 L 1224 836" stroke="#141a34" stroke-width="2"/>
  <path d="M1146 780 C 1142 740 1152 712 1170 702 L 1206 702 C 1226 712 1232 744 1226 780 Z" fill="#e6e2ea"/>
  <path d="M1206 702 C 1226 712 1232 744 1226 780 L 1210 780 C 1214 748 1210 720 1200 704 Z" fill="#b8b2c4"/>
  <path d="M1156 704 L 1218 704 L 1212 744 L 1162 744 Z" fill="#1f2747"/>
  <path d="M1162 736 L 1212 736" stroke="#fff" stroke-width="2"/>
  <path class="flutter" d="M1178 708 C 1156 714 1134 722 1112 718 C 1132 730 1158 726 1182 716 Z" fill="#d4202c"/>
  <path d="M1218 714 C 1242 690 1268 650 1290 616" stroke="#e6e2ea" stroke-width="22" stroke-linecap="round" fill="none"/>
  <circle cx="1294" cy="608" r="10" fill="#f0d0c0"/>
  <path d="M1150 716 C 1144 740 1142 760 1146 784" stroke="#d8d2de" stroke-width="20" stroke-linecap="round" fill="none"/>
  <rect x="1176" y="680" width="18" height="24" fill="#e8c8b8"/>
  <circle cx="1186" cy="664" r="32" fill="#141018"/>
  <path d="M1156 660 C 1150 630 1176 618 1196 624 C 1214 630 1222 650 1216 676 L 1206 690 L 1198 680 L 1186 692 L 1176 680 L 1166 690 Z" fill="#1a1520"/>
  <path d="M1212 640 C 1222 652 1222 668 1214 682" stroke="#7ec8ff" stroke-width="3" fill="none" opacity=".8"/>
  <path d="M1290 610 C 1296 600 1300 590 1296 580" stroke="#7ec8ff" stroke-width="2" fill="none" opacity=".7"/>
</g>
</svg>`;
  }

  // ---------- 第四幕 · 选拔（2066，彼岸计划） ----------
  function selection() {
    const r = rng(41);
    let ghosts = '';
    for (let row = 0; row < 3; row++) {
      for (let i = 0; i < 34; i++) {
        const x = 20 + i * 48 + (row % 2) * 22 + r() * 10, y = 800 + row * 22, h = 70 + row * 10;
        ghosts += person(x, y, h, '#9fd6e8', `class="ghost" style="animation-delay:${f(-r() * 6)}s;animation-duration:${f(4 + r() * 5)}s"`);
      }
    }
    let lattice = '';
    for (let y = 160; y < 820; y += 44) lattice += `<line x1="1230" y1="${y}" x2="1300" y2="${y + 44}"/><line x1="1300" y1="${y}" x2="1230" y2="${y + 44}"/><line x1="1230" y1="${y}" x2="1300" y2="${y}"/>`;
    const crew = [260, 355, 450, 640, 735, 830];
    const crewSvg = crew.map((x) => person(x, 962, 250, '#0d1a22')).join('') +
      crew.map((x) => `<path d="M${x + 30} ${962 - 210} C ${x + 44} ${962 - 140} ${x + 46} ${962 - 70} ${x + 42} 962" stroke="#5ff0ff" stroke-width="2.5" fill="none" opacity=".55"/>`).join('');
    return `<svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<defs>
  <linearGradient id="p4sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#020812"/><stop offset=".6" stop-color="#0b2534"/><stop offset="1" stop-color="#174052"/></linearGradient>
  <linearGradient id="p4cone" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#e8fbff" stop-opacity=".5"/><stop offset="1" stop-color="#e8fbff" stop-opacity="0"/></linearGradient>
  <linearGradient id="p4body" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f4f7fa"/><stop offset=".55" stop-color="#dfe5ec"/><stop offset="1" stop-color="#8e9cad"/></linearGradient>
  <linearGradient id="p4suit" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#f0f2f6"/><stop offset="1" stop-color="#a8b4c4"/></linearGradient>
  <filter id="p4blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="10"/></filter>
</defs>
<rect width="1600" height="1000" fill="url(#p4sky)"/>
${stars(r, 220, 0, 0, 1600, 560, 1.8)}
<g style="mix-blend-mode:screen">
  <path class="sweep" style="transform-origin:300px 880px;animation-duration:11s" d="M300 880 L 120 -40 L 520 -40 Z" fill="url(#p4cone)"/>
  <path class="sweep" style="transform-origin:1480px 880px;animation-duration:13s;animation-direction:alternate-reverse" d="M1480 880 L 1240 -40 L 1620 -40 Z" fill="url(#p4cone)"/>
</g>
<!-- 发射塔 -->
<g stroke="#0a1620" stroke-width="5" fill="none">${lattice}<line x1="1230" y1="150" x2="1230" y2="860"/><line x1="1300" y1="150" x2="1300" y2="860"/>
  <line x1="1150" y1="300" x2="1230" y2="300" stroke-width="10"/><line x1="1170" y1="520" x2="1230" y2="520" stroke-width="10"/></g>
<circle class="blinkred" cx="1265" cy="140" r="7" fill="#ff3030"/>
<circle class="blinkred" style="animation-delay:-.7s" cx="1265" cy="480" r="5" fill="#ff3030"/>
<!-- 火箭「彼岸号」 -->
<g>
  <path d="M1020 420 L 1056 420 L 1056 820 L 1020 820 Z" fill="url(#p4body)"/><path d="M1020 420 Q 1038 360 1056 420 Z" fill="#dfe5ec"/>
  <path d="M1144 420 L 1180 420 L 1180 820 L 1144 820 Z" fill="url(#p4body)"/><path d="M1144 420 Q 1162 360 1180 420 Z" fill="#dfe5ec"/>
  <path d="M1056 230 L 1144 230 L 1144 830 L 1056 830 Z" fill="url(#p4body)"/>
  <path d="M1056 232 Q 1100 70 1144 232 Z" fill="url(#p4body)"/>
  <rect x="1056" y="250" width="88" height="10" fill="#1a1f28"/>
  <rect x="1056" y="560" width="88" height="14" fill="#1a1f28"/>
  <rect x="1056" y="700" width="88" height="8" fill="#1a1f28"/>
  <g fill="#c8141e" font-family="Noto Serif SC, serif" font-weight="900" font-size="40" text-anchor="middle"><text x="1100" y="340">彼</text><text x="1100" y="390">岸</text></g>
  <circle cx="1100" cy="470" r="22" fill="none" stroke="#1a1f28" stroke-width="4"/><circle cx="1100" cy="470" r="7" fill="#c8141e"/>
  <path d="M1060 830 L 1076 860 L 1124 860 L 1140 830 Z" fill="#3a3f48"/>
</g>
<g filter="url(#p4blur)" opacity=".95">
  ${cloud(930, 860, 1.2, '#e8f4f8', '#8ab0c4', '#ffffff')}
  ${cloud(1160, 870, 1.0, '#e8f4f8', '#8ab0c4', '#ffffff')}
</g>
<rect y="880" width="1600" height="120" fill="#03090e"/>
<g fill="#ffd27a">${Array.from({ length: 30 }, (_, i) => `<circle cx="${i * 56 + 10}" cy="${900 + (i % 3) * 4}" r="2.5" opacity=".8"/>`).join('')}</g>
<g transform="translate(0 -92)">
<!-- 一万两千名候选人：落选者化作幽影 -->
<g>${ghosts}</g>
${crewSvg}
<!-- 遥（二十五岁）：白色飞行服，腋下夹着头盔 -->
<g>
  <path d="M500 640 C 470 648 452 680 448 706 C 470 690 486 680 506 676 Z" fill="#1a1a24"/>
  <path d="M520 962 L 516 820 L 540 820 L 542 962 Z M 556 962 L 558 820 L 582 820 L 584 962 Z" fill="#c8d0dc"/>
  <path d="M500 830 C 494 760 500 712 520 694 L 582 694 C 604 712 610 760 604 830 Z" fill="url(#p4suit)"/>
  <rect x="500" y="770" width="104" height="10" fill="#ff7a2a"/>
  <rect x="524" y="712" width="22" height="14" fill="#c8141e"/>
  <circle cx="612" cy="770" r="40" fill="#e8ecf2"/><path d="M584 760 A 32 30 0 0 1 640 760 L 636 784 L 588 784 Z" fill="#1a2a3a"/>
  <path d="M592 762 A 26 22 0 0 1 616 746" stroke="#8ff0ff" stroke-width="3" fill="none"/>
  <path d="M600 700 C 610 730 612 750 600 770" stroke="#d8dee8" stroke-width="20" stroke-linecap="round" fill="none"/>
  <rect x="540" y="664" width="22" height="32" fill="#f0d0c0"/>
  <circle cx="551" cy="642" r="32" fill="#1a1a24"/>
  <path d="M520 640 C 516 610 540 600 560 604 C 580 610 586 630 582 654 L 572 662 L 564 652 L 552 664 L 540 652 L 530 662 Z" fill="#20202c"/>
  <path d="M584 620 C 590 640 588 660 580 676" stroke="#5ff0ff" stroke-width="3" fill="none" opacity=".85"/>
</g>
<!-- 审视的瞄准框 -->
<g class="reticle" fill="none" stroke="#5ff0ff" stroke-width="3">
  <path d="M470 590 L 470 570 L 490 570 M 640 570 L 660 570 L 660 590 M 660 950 L 660 970 L 640 970 M 490 970 L 470 970 L 470 950"/>
</g>
<text x="680" y="590" font-family="monospace" font-size="18" fill="#5ff0ff">适格者 #07 · 天野 遥</text>
<text x="680" y="614" font-family="monospace" font-size="14" fill="#5ff0ff" opacity=".7">心理稳定度 0.98 / 孤独耐受 S</text>
</g>
<g font-family="monospace" fill="#5ff0ff">
  <text x="50" y="70" font-size="22">PROJECT HIGAN // 彼岸计划</text>
  <text x="50" y="104" font-size="16" opacity=".8">候选人 12,000 → 7</text>
  <text x="50" y="130" font-size="16" opacity=".8">目标：比邻星 b · 4.24 光年</text>
  <rect x="50" y="146" width="260" height="6" fill="#0b2a36"/><rect x="50" y="146" width="250" height="6" fill="#5ff0ff" class="shimmer"/>
</g>
</svg>`;
  }

  // ---------- 第五幕 · 升空（2069） ----------
  function launch() {
    const r = rng(51);
    let smoke = '';
    for (let i = 0; i < 9; i++) smoke += cloud(160 + i * 160 + r() * 40, 830 + r() * 50, 1.1 + r() * 0.7, '#fff3ea', '#d8a6b8', '#ffffff');
    let column = '';
    for (let i = 0; i < 10; i++) {
      const t = i / 9;
      column += `<circle cx="${f(800 - t * 140 + Math.sin(t * 5) * 30)}" cy="${f(420 + t * 400)}" r="${f(26 + t * 90)}" fill="${i % 2 ? '#fff0e6' : '#f6d8d8'}"/>`;
    }
    let speed = '';
    for (let i = 0; i < 40; i++) {
      const a = r() * Math.PI * 2, d1 = 160 + r() * 140, d2 = d1 + 120 + r() * 300;
      speed += `<line x1="${f(800 + Math.cos(a) * d1)}" y1="${f(300 + Math.sin(a) * d1)}" x2="${f(800 + Math.cos(a) * d2)}" y2="${f(300 + Math.sin(a) * d2)}"/>`;
    }
    let crowd = '';
    for (let i = 0; i < 26; i++) {
      const x = -20 + i * 66 + r() * 20, h = 180 + r() * 90;
      crowd += person(x, 1040, h, '#140a1a');
      if (r() < 0.45) {
        const s = r() < 0.5 ? -1 : 1;
        crowd += `<path d="M${f(x + s * h * 0.12)} ${f(1040 - h * 0.62)} L ${f(x + s * h * 0.3)} ${f(1040 - h * 1.15)}" stroke="#140a1a" stroke-width="${f(h * 0.08)}" stroke-linecap="round"/>`;
      }
    }
    return `<svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<defs>
  <linearGradient id="p5sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#161040"/><stop offset=".35" stop-color="#5a3488"/><stop offset=".65" stop-color="#ff7e5a"/><stop offset=".82" stop-color="#ffd59a"/></linearGradient>
  <linearGradient id="p5flame" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffffff"/><stop offset=".25" stop-color="#fff2a0"/><stop offset=".6" stop-color="#ff9a3a"/><stop offset="1" stop-color="#ff4a2a" stop-opacity="0"/></linearGradient>
  <radialGradient id="p5glow"><stop offset="0" stop-color="#fff2c0" stop-opacity=".9"/><stop offset="1" stop-color="#ff8a3a" stop-opacity="0"/></radialGradient>
  <filter id="p5blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="3"/></filter>
</defs>
<rect width="1600" height="1000" fill="url(#p5sky)"/>
${stars(r, 120, 0, 0, 1600, 300, 1.5)}
<!-- 天幕上的巨眼 -->
<g opacity=".55">
  <path d="M260 150 Q 800 -170 1340 150 Q 800 380 260 150 Z" fill="#2a0a2a" opacity=".55"/>
  <path d="M260 150 Q 800 -170 1340 150 Q 800 380 260 150 Z" fill="none" stroke="#ff6a5a" stroke-width="3"/>
  <circle cx="800" cy="140" r="110" fill="#7a0c18" opacity=".8"/>
  <ellipse cx="800" cy="140" rx="16" ry="86" fill="#0a0004"/>
</g>
${cloud(120, 260, 1.4, '#ffd0c0', '#c88aa8', '#fff0e6')}
${cloud(1250, 220, 1.6, '#ffd0c0', '#c88aa8', '#fff0e6')}
${cloud(560, 360, 0.9, '#ffc8b8', '#c88aa8', '#fff0e6')}
<g stroke="#fff" stroke-width="2" opacity=".25">${speed}</g>
<g class="rise">
  <g>${column}</g>
  <circle cx="800" cy="420" r="120" fill="url(#p5glow)"/>
  <path class="flicker" d="M780 360 C 770 420 784 480 800 540 C 816 480 830 420 820 360 Z" fill="url(#p5flame)"/>
  <!-- 遥光号 -->
  <g>
    <path d="M784 200 Q 800 140 816 200 L 816 360 L 784 360 Z" fill="#f4f6fa"/>
    <path d="M800 160 Q 816 180 816 200 L 816 360 L 802 360 Z" fill="#b8c2d0"/>
    <rect x="784" y="250" width="32" height="5" fill="#1a1f28"/>
    <path d="M784 330 L 768 368 L 784 362 Z M 816 330 L 832 368 L 816 362 Z" fill="#c8141e"/>
  </g>
</g>
<g filter="url(#p5blur)">${smoke}</g>
<rect y="930" width="1600" height="70" fill="#2a1424"/>
<!-- 送行的人群 -->
<g>${crowd}</g>
<!-- 母亲：举起一条红围巾 -->
<g>
  ${person(470, 1040, 300, '#1e0e22')}
  <path d="M500 860 L 560 690" stroke="#1e0e22" stroke-width="24" stroke-linecap="round"/>
  <path class="flutter" d="M556 694 C 600 680 640 700 680 690 C 650 712 610 716 566 712 Z" fill="#d4202c"/>
  <path d="M440 790 C 430 830 430 880 436 920" stroke="#ffb07a" stroke-width="3" fill="none" opacity=".7"/>
  <path d="M432 762 C 420 800 418 850 426 900" stroke="#1e0e22" stroke-width="16" fill="none"/>
</g>
</svg>`;
  }

  // ---------- 第六幕 · 长夜（2069—2111，冷冻休眠） ----------
  function longNight() {
    const r = rng(61);
    let streaks = '';
    for (let i = 0; i < 46; i++) {
      const a = r() * Math.PI * 2, d = 40 + r() * 60;
      streaks += `<line class="streak" style="animation-delay:${f(-r() * 1.6)}s" x1="${f(800 + Math.cos(a) * d)}" y1="${f(130 + Math.sin(a) * d * 0.25)}" x2="${f(800 + Math.cos(a) * 700)}" y2="${f(130 + Math.sin(a) * 175)}"/>`;
    }
    let bubbles = '';
    for (let i = 0; i < 26; i++) bubbles += `<circle class="bubble" style="animation-delay:${f(-r() * 6)}s;animation-duration:${f(4 + r() * 4)}s" cx="${f(680 + r() * 240)}" cy="${f(860 + r() * 30)}" r="${f(2 + r() * 6)}" fill="none" stroke="#bff6ff" stroke-width="1.5"/>`;
    let frost = '';
    for (let i = 0; i < 90; i++) {
      const side = r() < 0.5 ? 0 : 1;
      frost += `<circle cx="${f(side ? 900 + r() * 40 : 660 + r() * 40)}" cy="${f(170 + r() * 700)}" r="${f(0.8 + r() * 2.5)}" fill="#fff" opacity="${(0.3 + r() * 0.6).toFixed(2)}"/>`;
    }
    const bars = Array.from({ length: 18 }, (_, i) => {
      const h = 20 + (i * 37) % 40;
      return `<rect class="bar-anim" style="animation-delay:${f(-i * 0.13)}s" x="${1170 + i * 12}" y="${340 - h}" width="7" height="${h}" fill="#7ef0ff"/>`;
    }).join('');
    return `<svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<defs>
  <linearGradient id="p6wall" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#050a16"/><stop offset="1" stop-color="#0c1830"/></linearGradient>
  <linearGradient id="p6liquid" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#7ee8ff" stop-opacity=".55"/><stop offset=".5" stop-color="#1a7ab0" stop-opacity=".5"/><stop offset="1" stop-color="#06304a" stop-opacity=".85"/></linearGradient>
  <linearGradient id="p6glass" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#fff" stop-opacity=".22"/><stop offset=".2" stop-color="#fff" stop-opacity="0"/><stop offset=".8" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".16"/></linearGradient>
  <linearGradient id="p6fade" x1="0" y1="0" x2="0" y2="1"><stop offset=".45" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
  <mask id="p6mask"><rect width="1600" height="1000" fill="url(#p6fade)"/></mask>
  <radialGradient id="p6halo"><stop offset="0" stop-color="#6fe6ff" stop-opacity=".45"/><stop offset="1" stop-color="#6fe6ff" stop-opacity="0"/></radialGradient>
  <clipPath id="p6pod"><rect x="660" y="160" width="280" height="720" rx="140"/></clipPath>
  <clipPath id="p6view"><rect x="120" y="50" width="1360" height="160" rx="30"/></clipPath>
</defs>
<rect width="1600" height="1000" fill="url(#p6wall)"/>
<!-- 舷窗：星光被拉成长线 -->
<g clip-path="url(#p6view)">
  <rect x="120" y="50" width="1360" height="160" fill="#01030a"/>
  <g stroke="#cfe8ff" stroke-width="1.6" opacity=".8">${streaks}</g>
</g>
<rect x="120" y="50" width="1360" height="160" rx="30" fill="none" stroke="#1c2a44" stroke-width="10"/>
<!-- 两侧的同伴休眠舱 -->
<g opacity=".55">
  <rect x="300" y="300" width="170" height="460" rx="85" fill="#0c2a40" stroke="#1d4664" stroke-width="6"/>
  <rect x="1130" y="300" width="170" height="460" rx="85" fill="#0c2a40" stroke="#1d4664" stroke-width="6"/>
  ${person(385, 700, 330, '#062030')}${person(1215, 700, 330, '#062030')}
</g>
<circle cx="800" cy="520" r="420" fill="url(#p6halo)"/>
<!-- 主休眠舱 -->
<rect x="646" y="146" width="308" height="748" rx="154" fill="#0a1420" stroke="#2a4a66" stroke-width="10"/>
<g clip-path="url(#p6pod)">
  <rect x="660" y="160" width="280" height="720" fill="url(#p6liquid)"/>
  <g mask="url(#p6mask)">
    <!-- 在液体中漂浮的长发 -->
    <path class="flutter" style="animation-duration:5s;animation-delay:-0.0s" d="M742 300 C 703 250 657 220 651 180 C 645 180 612 170 606 163" fill="none" stroke="#2a4a8a" stroke-width="9" stroke-linecap="round"/><path class="flutter" style="animation-duration:6s;animation-delay:-0.4s" d="M752 300 C 719 250 678 220 676 184 C 674 180 643 170 638 161" fill="none" stroke="#1a2c5a" stroke-width="14" stroke-linecap="round"/><path class="flutter" style="animation-duration:7s;animation-delay:-0.8s" d="M761 300 C 735 250 698 220 701 187 C 703 180 675 170 670 159" fill="none" stroke="#1a2c5a" stroke-width="9" stroke-linecap="round"/><path class="flutter" style="animation-duration:8s;animation-delay:-1.2s" d="M771 300 C 752 250 718 220 726 190 C 732 180 706 170 703 156" fill="none" stroke="#2a4a8a" stroke-width="14" stroke-linecap="round"/><path class="flutter" style="animation-duration:5s;animation-delay:-1.6s" d="M781 300 C 768 250 739 220 750 194 C 762 180 737 170 735 154" fill="none" stroke="#1a2c5a" stroke-width="9" stroke-linecap="round"/><path class="flutter" style="animation-duration:6s;animation-delay:-2.0s" d="M790 300 C 784 250 760 220 775 197 C 791 180 769 170 768 152" fill="none" stroke="#1a2c5a" stroke-width="14" stroke-linecap="round"/><path class="flutter" style="animation-duration:7s;animation-delay:-2.4s" d="M800 300 C 800 250 780 220 800 200 C 820 180 800 170 800 150" fill="none" stroke="#2a4a8a" stroke-width="9" stroke-linecap="round"/><path class="flutter" style="animation-duration:8s;animation-delay:-2.8s" d="M810 300 C 816 250 800 220 825 197 C 849 180 831 170 832 152" fill="none" stroke="#1a2c5a" stroke-width="14" stroke-linecap="round"/><path class="flutter" style="animation-duration:5s;animation-delay:-3.2s" d="M819 300 C 832 250 821 220 850 194 C 878 180 863 170 865 154" fill="none" stroke="#1a2c5a" stroke-width="9" stroke-linecap="round"/><path class="flutter" style="animation-duration:6s;animation-delay:-3.6s" d="M829 300 C 848 250 842 220 874 190 C 908 180 894 170 897 156" fill="none" stroke="#2a4a8a" stroke-width="14" stroke-linecap="round"/><path class="flutter" style="animation-duration:7s;animation-delay:-4.0s" d="M839 300 C 865 250 862 220 899 187 C 937 180 925 170 930 159" fill="none" stroke="#1a2c5a" stroke-width="9" stroke-linecap="round"/><path class="flutter" style="animation-duration:8s;animation-delay:-4.4s" d="M848 300 C 881 250 882 220 924 184 C 966 180 957 170 962 161" fill="none" stroke="#1a2c5a" stroke-width="14" stroke-linecap="round"/><path class="flutter" style="animation-duration:5s;animation-delay:-4.8s" d="M858 300 C 897 250 903 220 949 180 C 995 180 988 170 994 163" fill="none" stroke="#2a4a8a" stroke-width="9" stroke-linecap="round"/>
    <path d="M740 330 C 720 250 760 196 800 196 C 840 196 880 250 860 330 C 870 290 860 250 840 240 C 820 260 780 260 760 240 C 740 250 730 290 740 330 Z" fill="#1a2c5a"/>
    <path d="M760 220 C 770 200 790 192 800 194" stroke="#7ee8ff" stroke-width="3" fill="none" opacity=".7"/>
    <path d="M720 520 C 700 470 712 420 742 400 L 858 400 C 888 420 900 470 880 520 L 900 880 L 700 880 Z" fill="#dfeaf2"/>
    <path d="M800 410 L 800 880 M 742 470 L 858 470" stroke="#5ac8e8" stroke-width="3" opacity=".7"/>
    <rect x="784" y="380" width="32" height="36" fill="#e8d0c8"/>
    <ellipse cx="800" cy="340" rx="52" ry="62" fill="#f2dcd4"/>
    <path d="M748 320 C 750 270 790 258 806 262 C 830 266 856 286 852 330 C 840 304 826 296 816 300 C 806 312 790 316 774 312 C 764 320 756 326 748 320 Z" fill="#1a2c5a"/>
    <path d="M770 350 Q 782 358 794 350 M 806 350 Q 818 358 830 350" stroke="#2a2040" stroke-width="2.8" fill="none" stroke-linecap="round"/>
    <path d="M771 351 L 768 356 M 777 355 L 775 360 M 823 355 L 825 360 M 829 351 L 832 356" stroke="#2a2040" stroke-width="1.6"/>
    <path d="M794 384 Q 800 387 806 384" stroke="#b07080" stroke-width="2" fill="none" stroke-linecap="round"/>
    <ellipse cx="772" cy="368" rx="9" ry="3.5" fill="#ff9aaa" opacity=".35"/><ellipse cx="828" cy="368" rx="9" ry="3.5" fill="#ff9aaa" opacity=".35"/>
  </g>
  ${bubbles}
  <rect x="660" y="160" width="280" height="720" fill="url(#p6glass)"/>
  ${frost}
</g>
<path d="M700 200 C 690 400 690 600 700 820" stroke="#fff" stroke-width="5" opacity=".18" fill="none"/>
<rect x="740" y="880" width="120" height="40" rx="6" fill="#0a1420" stroke="#2a4a66" stroke-width="4"/>
<text x="800" y="907" font-family="monospace" font-size="16" fill="#7ef0ff" text-anchor="middle">CRYO-07</text>
<!-- 左侧仪表 -->
<g font-family="monospace" fill="#7ef0ff">
  <rect x="80" y="280" width="250" height="210" rx="8" fill="#04121e" stroke="#1d4664" stroke-width="2"/>
  <text x="100" y="316" font-size="18">冷冻休眠 · 稳定</text>
  <text x="100" y="350" font-size="15" opacity=".8">心率   4 bpm</text>
  <text x="100" y="378" font-size="15" opacity=".8">体温   3.2 °C</text>
  <text x="100" y="406" font-size="15" opacity=".8">航程   0.1 c</text>
  <rect x="100" y="430" width="210" height="10" fill="#0b2a36"/>
  <rect x="100" y="430" width="0" height="10" fill="#7ef0ff"><animate attributeName="width" from="0" to="210" dur="40s" fill="freeze"/></rect>
  <text x="100" y="468" font-size="13" opacity=".6">地球 → 比邻星 b · 4.24 ly</text>
</g>
<!-- 来自地球的讯息 -->
<g class="msg" font-family="monospace" fill="#7ef0ff">
  <rect x="1150" y="200" width="300" height="190" rx="8" fill="#04121e" stroke="#7ef0ff" stroke-width="1.5" stroke-dasharray="6 4"/>
  <text x="1170" y="232" font-size="16">▶ 讯息 · 来自地球</text>
  <text x="1170" y="258" font-size="13" opacity=".7">延迟 4.24 年 · 发送人：母亲</text>
  ${bars}
  <text x="1170" y="370" font-size="13" opacity=".7">「院子里的樱花开了。」</text>
</g>
</svg>`;
  }

  // ---------- 第七幕 · 彼岸（2111，比邻星 b） ----------
  function otherShore() {
    const r = rng(71);
    let crystals = '';
    const cl = [[120, 1000, 1.2], [260, 1000, 0.9], [1380, 1000, 1.3], [1500, 1000, 1.0], [1260, 1000, 0.7], [40, 1000, 0.8]];
    for (const [x, y, s] of cl) {
      for (let k = 0; k < 5; k++) {
        const w = (18 + r() * 22) * s, h = (140 + r() * 220) * s, dx = (r() - 0.5) * 120 * s, tilt = (r() - 0.5) * 30;
        crystals += `<g transform="translate(${f(x + dx)} ${y}) rotate(${f(tilt)})" class="shimmer" style="animation-delay:${f(-r() * 4)}s"><path d="M${f(-w)} 0 L ${f(-w * 0.8)} ${f(-h * 0.8)} L 0 ${f(-h)} L ${f(w * 0.8)} ${f(-h * 0.8)} L ${f(w)} 0 Z" fill="url(#p7crys)"/><path d="M0 ${f(-h)} L ${f(w * 0.2)} 0 L ${f(w)} 0 L ${f(w * 0.8)} ${f(-h * 0.8)} Z" fill="#2a0a4a" opacity=".35"/></g>`;
      }
    }
    let rocks = '';
    for (const [x, y, s] of [[300, 300, 1], [1000, 240, 0.7], [1420, 380, 0.5]]) {
      rocks += `<g class="float" style="animation-delay:${f(-r() * 6)}s"><path d="M${x - 80 * s} ${y} L ${x + 90 * s} ${y} L ${x + 50 * s} ${y + 70 * s} L ${x} ${y + 120 * s} L ${x - 50 * s} ${y + 60 * s} Z" fill="#2a0f2e"/><path d="M${x - 80 * s} ${y} L ${x + 90 * s} ${y} L ${x + 80 * s} ${y - 12 * s} L ${x - 70 * s} ${y - 14 * s} Z" fill="#7a2a4a"/></g>`;
    }
    let reflect = '';
    for (let i = 0; i < 22; i++) {
      const y = 680 + i * 14, w = 260 - i * 6 + r() * 60;
      reflect += `<rect class="shimmer" style="animation-delay:${f(-r() * 4)}s" x="${f(1150 - w / 2 + (r() - 0.5) * 40)}" y="${y}" width="${f(w)}" height="3" fill="#ffb07a" opacity="${(0.25 + r() * 0.4).toFixed(2)}"/>`;
    }
    return `<svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<defs>
  <linearGradient id="p7sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0e0420"/><stop offset=".35" stop-color="#3e0c3c"/><stop offset=".6" stop-color="#a62c58"/><stop offset=".68" stop-color="#ff7a4a"/></linearGradient>
  <radialGradient id="p7sun"><stop offset="0" stop-color="#ffe0b0"/><stop offset=".55" stop-color="#ff6a3a"/><stop offset=".9" stop-color="#c81e2a"/><stop offset="1" stop-color="#8a0a1e"/></radialGradient>
  <radialGradient id="p7corona"><stop offset=".5" stop-color="#ff5a3a" stop-opacity=".55"/><stop offset="1" stop-color="#ff5a3a" stop-opacity="0"/></radialGradient>
  <linearGradient id="p7sea" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#5a1a50"/><stop offset="1" stop-color="#14051e"/></linearGradient>
  <linearGradient id="p7crys" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#3a1a7a"/><stop offset=".55" stop-color="#5ae6ff"/><stop offset="1" stop-color="#ffc8f0"/></linearGradient>
  <linearGradient id="p7suit" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#8a7a9a"/><stop offset=".55" stop-color="#e8e2ee"/><stop offset="1" stop-color="#ffb0a0"/></linearGradient>
  <linearGradient id="p7visor" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2a0a2a"/><stop offset=".5" stop-color="#ff7a4a"/><stop offset="1" stop-color="#ffe0a0"/></linearGradient>
  <radialGradient id="p7iris"><stop offset="0" stop-color="#ffb02e"/><stop offset=".45" stop-color="#d81e1e"/><stop offset="1" stop-color="#300008"/></radialGradient>
  <filter id="p7blur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="12"/></filter>
  <filter id="p7glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="1600" height="1000" fill="url(#p7sky)"/>
${stars(r, 160, 0, 0, 1600, 380, 1.8)}
<g filter="url(#p7glow)">${sparkle(260, 120, 20, '#fff8e0', 'class="tw"')}${sparkle(300, 150, 12, '#ffe0a0', 'class="tw" style="animation-delay:-1s"')}</g>
<!-- 天空睁开的眼 -->
<g class="sky-eye" style="transition:transform 3s cubic-bezier(.2,.8,.2,1)">
  <path d="M420 230 Q 800 -40 1180 230 Q 800 420 420 230 Z" fill="#f3dccc" opacity=".92"/>
  <circle cx="800" cy="220" r="118" fill="url(#p7iris)"/>
  <ellipse cx="800" cy="220" rx="14" ry="92" fill="#080002"/>
  <ellipse cx="760" cy="176" rx="22" ry="12" fill="#fff" opacity=".8"/>
  <g stroke="#a0101e" stroke-width="2" fill="none" opacity=".7"><path d="M430 232 C 500 228 540 210 600 214"/><path d="M1170 232 C 1100 240 1060 222 1000 230"/><path d="M450 240 C 520 260 560 250 610 262"/></g>
  <path d="M420 230 Q 800 -40 1180 230" fill="none" stroke="#1a0306" stroke-width="8"/>
  <path d="M420 230 Q 800 420 1180 230" fill="none" stroke="#1a0306" stroke-width="4"/>
</g>
<g filter="url(#p7blur)" opacity=".8">
  ${cloud(240, 360, 1.3, '#7a2a5a', '#4a1240', '#c85a7a')}
  ${cloud(1100, 400, 1.6, '#7a2a5a', '#4a1240', '#c85a7a')}
</g>
${rocks}
<!-- 比邻星：永远悬在同一个位置的红色太阳 -->
<circle cx="1150" cy="620" r="330" fill="url(#p7corona)"/>
<circle cx="1150" cy="620" r="210" fill="url(#p7sun)"/>
<g fill="#a01a1e" opacity=".35"><ellipse cx="1090" cy="560" rx="30" ry="14"/><ellipse cx="1200" cy="650" rx="22" ry="10"/><ellipse cx="1160" cy="520" rx="14" ry="7"/></g>
<rect y="660" width="1600" height="340" fill="url(#p7sea)"/>
<rect y="658" width="1600" height="4" fill="#ffb07a" opacity=".6"/>
${reflect}
<!-- 远处着陆的遥光号 -->
<g transform="translate(980 650)"><path d="M-10 0 L -6 -40 Q 0 -60 6 -40 L 10 0 Z" fill="#20101e"/><path d="M-18 0 L -8 -14 M 18 0 L 8 -14" stroke="#20101e" stroke-width="4"/><circle cx="0" cy="-30" r="2.5" fill="#7ef0ff" class="blinkred"/></g>
${crystals}
<!-- 悬崖 -->
<path d="M0 1000 L 0 760 C 120 740 300 760 420 754 C 560 748 680 760 760 772 L 800 820 L 780 1000 Z" fill="#1c0820"/>
<path d="M0 760 C 120 740 300 760 420 754 C 560 748 680 760 760 772" fill="none" stroke="#ff7a5a" stroke-width="3" opacity=".6"/>
<!-- 宇航员遥：仰望天空 -->
<g>
  <rect x="520" y="618" width="46" height="90" rx="10" fill="#6a5a7a"/>
  <path d="M560 770 L 556 700 L 578 700 L 584 770 Z M 592 770 L 594 700 L 616 700 L 618 770 Z" fill="url(#p7suit)"/>
  <path d="M548 772 L 586 772 L 588 760 L 552 760 Z M 588 772 L 626 772 L 624 760 L 590 760 Z" fill="#4a3a5a"/>
  <path d="M548 712 C 540 660 552 622 576 610 L 612 610 C 636 622 640 660 630 712 Z" fill="url(#p7suit)"/>
  <rect x="560" y="660" width="40" height="18" rx="3" fill="#4a3a5a"/><circle cx="572" cy="669" r="3" fill="#7ef0ff"/><circle cx="586" cy="669" r="3" fill="#ff5a5a"/>
  <path d="M626 630 C 650 650 660 680 654 706" stroke="url(#p7suit)" stroke-width="20" stroke-linecap="round" fill="none"/>
  <circle cx="594" cy="576" r="44" fill="url(#p7suit)"/>
  <g transform="rotate(-28 594 576)"><ellipse cx="612" cy="576" rx="26" ry="30" fill="url(#p7visor)"/></g>
  <path d="M606 556 C 616 550 626 554 630 562" stroke="#fff" stroke-width="3" fill="none" opacity=".8"/>
  ${sparkle(624, 560, 9, '#fff', 'class="tw"')}
  <path d="M636 570 C 640 590 636 610 628 622" stroke="#ffb0a0" stroke-width="3" fill="none"/>
</g>
</svg>`;
  }

  // ---------- 终幕 · 凝视（2112，又一个孩子） ----------
  function epilogue() {
    const r = rng(81);
    let motes = '';
    for (let i = 0; i < 50; i++) motes += `<circle class="firefly" style="animation-delay:${f(-r() * 5)}s" cx="${f(r() * 1600)}" cy="${f(r() * 1000)}" r="${f(1 + r() * 2.5)}" fill="#ff8a7a" opacity=".6"/>`;
    let fibers = '';
    for (let i = 0; i < 70; i++) {
      const a = i / 70 * Math.PI * 2 + r() * 0.04;
      fibers += `<line x1="${f(800 + Math.cos(a) * 80)}" y1="${f(490 + Math.sin(a) * 80)}" x2="${f(800 + Math.cos(a) * (150 + r() * 20))}" y2="${f(490 + Math.sin(a) * (150 + r() * 20))}"/>`;
    }
    return `<svg viewBox="0 0 1600 1000" preserveAspectRatio="xMidYMid slice">
<defs>
  <radialGradient id="p8bg" cx=".5" cy=".5" r=".7"><stop offset="0" stop-color="#4a1e24"/><stop offset=".55" stop-color="#1e0a10"/><stop offset="1" stop-color="#050104"/></radialGradient>
  <linearGradient id="p8sclera" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8a8aa8"/><stop offset=".35" stop-color="#e8e6f2"/><stop offset="1" stop-color="#ffffff"/></linearGradient>
  <linearGradient id="p8iris" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0c0820"/><stop offset=".45" stop-color="#2a2a8a"/><stop offset=".8" stop-color="#4ab8f0"/><stop offset="1" stop-color="#a8f0ff"/></linearGradient>
  <clipPath id="p8clip"><path d="M340 520 C 520 290 1080 280 1270 470 C 1090 650 560 690 340 520 Z"/></clipPath>
  <filter id="p8glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
</defs>
<rect width="1600" height="1000" fill="url(#p8bg)"/>
${motes}
<g class="anime-eye">
  <path d="M340 520 C 520 290 1080 280 1270 470 C 1090 650 560 690 340 520 Z" fill="url(#p8sclera)"/>
  <g clip-path="url(#p8clip)">
    <circle cx="800" cy="490" r="170" fill="url(#p8iris)"/>
    <g stroke="#9ae0ff" stroke-width="1.5" opacity=".35">${fibers}</g>
    <circle cx="800" cy="490" r="170" fill="none" stroke="#0a0620" stroke-width="10"/>
    <circle cx="800" cy="490" r="70" fill="#05030c"/>
    <!-- 瞳孔里倒映着那只眼睛 -->
    <g class="reflect" filter="url(#p8glow)">
      <path d="M800 452 L 836 514 L 764 514 Z" fill="none" stroke="#f1d79a" stroke-width="3"/>
      <path d="M780 494 Q 800 478 820 494 Q 800 508 780 494 Z" fill="#f1d79a"/>
      <circle cx="800" cy="494" r="6" fill="#d81e1e"/>
    </g>
    <ellipse cx="722" cy="420" rx="48" ry="34" fill="#fff"/>
    <circle cx="880" cy="568" r="15" fill="#fff" opacity=".9"/>
    <circle cx="690" cy="470" r="7" fill="#fff" opacity=".8"/>
    <path d="M340 400 C 600 300 1000 300 1280 380 L 1280 280 L 340 280 Z" fill="#3a2a5a" opacity=".35"/>
  </g>
  <!-- 日漫式的粗上睫毛线 -->
  <path d="M320 536 C 470 300 1060 250 1290 452 C 1300 460 1300 470 1286 468 C 1070 300 520 320 352 528 Z" fill="#120a14"/>
  <path d="M1270 452 C 1300 430 1320 410 1336 380 C 1320 420 1300 446 1286 466 Z M 1240 418 C 1270 396 1290 370 1300 340 C 1290 380 1270 410 1256 432 Z" fill="#120a14"/>
  <path d="M380 548 C 600 640 1060 630 1250 482" fill="none" stroke="#3a1a24" stroke-width="5" stroke-linecap="round"/>
  <path d="M520 380 C 700 300 960 300 1120 360" fill="none" stroke="#120a14" stroke-width="3" opacity=".5"/>
</g>
</svg>`;
  }

  window.SCENES = { prologue, birth, curiosity, ladder, selection, launch, longNight, otherShore, epilogue };
})();
