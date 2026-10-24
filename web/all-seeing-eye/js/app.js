/* 全知之眼 · 主逻辑：剧本、眼睛、转场、氛围 */
(function () {
  'use strict';

  const S = window.SCENES;
  const $ = (s) => document.querySelector(s);
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // ---------- 剧本 ----------
  // eye.angle：眼睛围绕画框的位置（度，0 = 右，-90 = 上），像日晷一样随时间推移
  // open 睁开程度 / dil 瞳孔放大 / slit 竖瞳 / veins 血丝 / tension 压迫感（心跳、窥视者）
  // focus：眼睛默认凝视的画面坐标（1600×1000）
  const IT = '祂';
  const ACTS = [
    {
      num: '序幕', short: '序', title: '睁眼', year: null, scene: S.prologue, focus: [800, 500],
      eye: { angle: -90, scale: 1.25, open: 0.5, dil: 1, slit: 0.2, veins: 0.35, tension: 0.35, i1: '#ffcf6b', i2: '#8a1a08' },
      lines: [
        { t: '在时间开始之前，祂就已经睁着眼。' },
        { t: '祂不说话，也不伸手。祂只是看——看每一次降生，每一次攀登，每一次坠落。', fx: ['cosmos'] },
        { t: '人们把这道目光叫作命运、秩序，或者“社会”。', fx: ['narrow'] },
        { who: IT, t: '……今天，我看向一个孩子。', fx: ['widen', 'shake'] }
      ]
    },
    {
      num: '第一幕', short: '壹', title: '降生', year: 2041, scene: S.birth, focus: [742, 536],
      eye: { angle: 172, scale: 0.85, open: 0.95, dil: 1.25, slit: 0, veins: 0.1, tension: 0.15, i1: '#ffe08a', i2: '#9a4a10' },
      lines: [
        { t: '2041 年，春。海港城第七区下了一场不合时节的大雨。' },
        { t: '凌晨两点四十一分，妇产病房里，一个女孩降生了。' },
        { who: '母亲', t: '就叫你「遥」吧——遥远的遥。愿你能走得很远，很远。' },
        { t: '婴儿没有哭。她睁着眼睛，越过母亲的肩膀，望向窗外的雨幕。', fx: ['blink'] },
        { t: '仿佛在回望着什么。', fx: ['widen'] }
      ]
    },
    {
      num: '第二幕', short: '贰', title: '好奇', year: 2048, scene: S.curiosity, focus: [826, 640],
      eye: { angle: 196, scale: 0.9, open: 0.88, dil: 1.1, slit: 0.05, veins: 0.18, tension: 0.2, i1: '#ffc860', i2: '#8a2a08' },
      lines: [
        { t: '2048 年，遥七岁。她拆了家里的旧收音机，又用纸筒和两片放大镜做了第一架望远镜。' },
        { who: '遥', t: '妈妈，星星为什么不会掉下来？' },
        { who: '母亲', t: '因为它们都在很远很远的地方，被一根看不见的线牵着呀。' },
        { t: '每一个晴朗的夜晚，她都爬上公寓楼顶，一颗一颗地数星星，把它们的名字抄在笔记本上。' },
        { who: '遥', t: '如果星星的那一边也有人……他们现在，是不是也在看着我？' },
        { t: '天空没有回答。但在比星星更高的地方，有什么东西，眨了一下眼睛。', fx: ['blink', 'redflash'] }
      ]
    },
    {
      num: '第三幕', short: '叁', title: '阶梯', year: 2057, scene: S.ladder, focus: [1186, 664],
      eye: { angle: 256, scale: 1.0, open: 0.58, dil: 0.85, slit: 0.35, veins: 0.6, tension: 0.5, i1: '#ff9a3a', i2: '#6a0a08' },
      lines: [
        { t: '海港城被分成九层。每个人出生的那一刻，就被写进了一个编号。' },
        { t: '分数、出身、信用、评级……人们在阶梯上攀爬，或者跌落。没有人知道是谁在记录这一切。', fx: ['narrow'] },
        { t: '但每个人都感觉得到——那道从高处落下的目光。' },
        { who: IT, t: '编号 2041-0417。第六层。继续攀爬。', fx: ['widen', 'shake', 'watchers'] },
        { t: '十六岁的遥站在台阶上。她没有看向上一层，而是看向了云缝里那颗唯一有颜色的星。' },
        { who: '遥', t: '我不想只是往上爬。我想——往外走。', fx: ['narrow'] }
      ]
    },
    {
      num: '第四幕', short: '肆', title: '选拔', year: 2066, scene: S.selection, focus: [551, 700],
      eye: { angle: 286, scale: 1.05, open: 0.45, dil: 0.8, slit: 0.6, veins: 0.55, tension: 0.6, i1: '#ff7a3a', i2: '#4a0408' },
      lines: [
        { t: '2066 年，「彼岸计划」启动——人类第一次载人星际航行。目标：4.24 光年外的比邻星 b。' },
        { t: '一万两千名候选人。离心机、深海、孤独隔离舱，九百天的测试。' },
        { t: '落选者的名字一个接一个地熄灭。最终名单上，只剩下七个人。', fx: ['narrow'] },
        { who: '考官', t: '天野遥。你为什么要去一个可能永远回不来的地方？' },
        { who: '遥', t: '因为我想知道——在被注视的世界之外，还有什么。', fx: ['widen'] },
        { who: IT, t: '……去吧。无论多远，我都看得见。', fx: ['shake', 'redflash'] }
      ]
    },
    {
      num: '第五幕', short: '伍', title: '升空', year: 2069, scene: S.launch, focus: [800, 300],
      eye: { angle: 344, scale: 1.15, open: 1.0, dil: 0.7, slit: 0.2, veins: 0.8, tension: 0.75, i1: '#ff5a2a', i2: '#3a0006' },
      lines: [
        { t: '2069 年 4 月 7 日，凌晨 4 时 24 分。' },
        { t: '倒数归零。大地在颤抖，天空被烧成了橘红色。', fx: ['shake'] },
        { who: '母亲', t: '遥——！一定要看清楚啊——！' },
        { t: '「遥光号」刺破云层。她从舷窗回望，地球缩成了一粒蓝色的尘埃。' },
        { t: '而在更远的地方，一只巨大的眼睛，正静静地注视着这艘渺小的船。', fx: ['widen', 'watchers'] }
      ]
    },
    {
      num: '第六幕', short: '陆', title: '长夜', year: 2069, scene: S.longNight, focus: [800, 350],
      eye: { angle: 8, scale: 0.95, open: 0.4, dil: 1.3, slit: 0, veins: 0.3, tension: 0.3, i1: '#9fd8ff', i2: '#0b2a4a' },
      lines: [
        { t: '航程：四十二年。遥在冷冻舱里沉睡，心跳每分钟四次。' },
        { t: '地球上的日历一页一页地翻过。', year: 2075 },
        { t: '2081 年，一段讯息抵达飞船。它在真空里走了四年零三个月。', year: 2081, fx: ['msg'] },
        { who: '母亲', t: '遥，今天院子里的樱花开了。妈妈很好。你……看到什么了吗？' },
        { t: '2094 年，地球的讯息中断了。没有人知道为什么。', year: 2094, fx: ['nomsg'] },
        { t: '在没有一个人醒着的漫长黑夜里——', year: 2105 },
        { t: '连那只眼睛，也合上了。', year: 2111, fx: ['sleep'] }
      ]
    },
    {
      num: '第七幕', short: '柒', title: '彼岸', year: 2111, scene: S.otherShore, focus: [600, 570],
      eye: { angle: -90, scale: 1.55, open: 0.0, dil: 0.6, slit: 0.5, veins: 1, tension: 0.9, i1: '#ff3a2a', i2: '#2a0004' },
      lines: [
        { t: '2111 年。比邻星 b。' },
        { t: '红色的太阳永远悬在同一个位置。水晶般的植物在风里鸣响，像是遥远的钟声。' },
        { t: '遥走出舱门，在一个从未被人类踏足的世界上，留下了第一个脚印。' },
        { who: '遥', t: '妈妈……我看到了。我走得很远，很远了。' },
        { t: '她抬起头——', fx: ['wake'] },
        { t: '天空中，那只眼睛，睁开了。', fx: ['skyeye', 'widen', 'shake', 'redflash', 'watchers'] },
        { who: IT, t: '欢迎来到彼岸，遥。', fx: ['narrow'] },
        { t: '祂从来不属于地球。祂属于一切被注视之物——而被注视的，从来没有尽头。' }
      ]
    },
    {
      num: '终幕', short: '终', title: '凝视', year: 2112, scene: S.epilogue, focus: [800, 490],
      eye: { angle: -90, scale: 1.2, open: 0.85, dil: 0.9, slit: 0.4, veins: 0.9, tension: 0.85, i1: '#ff3a2a', i2: '#2a0004' },
      lines: [
        { t: '2112 年。海港城第七区。又下了一场不合时节的大雨。' },
        { t: '又一个孩子降生了。', fx: ['animeeye'] },
        { t: '她睁开眼睛，望向窗外——', fx: ['reflect'] },
        { t: '在她的瞳孔深处，倒映着一只眼睛。', fx: ['widen'] },
        { who: IT, t: '而现在——我看向了你。', fx: ['stare', 'shake', 'redflash', 'watchers'] }
      ]
    }
  ];

  // ---------- DOM ----------
  const stage = $('.stage');
  const dialog = $('.dialog');
  const whoEl = $('.dialog .who');
  const textEl = $('.dialog .text');
  const card = $('.titlecard');
  const hudAct = $('.hud .act-label');
  const hudYear = $('.hud .yr');
  const bigYear = $('#bigYear');
  const plate = $('.frame .plate');
  const timeline = $('.timeline');
  const eyeWrap = $('#eyeWrap');
  const eyeInner = $('#eyeInner');
  const frame = $('.frame');

  let actIdx = -1, lineIdx = -1;
  let currentScene = null;
  let typingTimer = null, typing = false, fullText = '';
  let busy = false, auto = false, autoTimer = null;
  let started = false, ended = false;
  const seen = new Set();

  // ---------- 全知之眼：绘制 ----------
  const W = 124, H = 64;
  const E = {
    o: 0, oT: 0, blinkUntil: 0, nextBlink: 0,
    ix: 0, iy: 0, dil: 1, dilT: 1, slit: 0.2, slitT: 0.2,
    tempOpen: null, tempUntil: 0, tempDil: null,
    tx: 0, ty: 0, mouseAt: -1e9, mx: 0, my: 0,
    sacX: 0, sacY: 0, nextSac: 0,
    tension: 0.3, staring: false,
    x: 0, y: 0, s: 1
  };
  buildEye();
  const clipPathEl = $('#eClipPath');
  const outlineEl = $('#eOutline');
  const creaseEl = $('#eCrease');
  const lowerEl = $('#eLower');
  const lashesEl = $('#eLashes');
  const irisEl = $('#eIrisG');
  const pupilEl = $('#ePupil');
  const medalIris = $('.frame .medal .m-iris');

  function lidCurves(o) {
    const up = -H * 1.3 * o + H * 0.16 * (1 - o);
    const lo = H * 0.95 * o + H * 0.16 * (1 - o);
    return { up, lo };
  }
  function bez(t, p0, p1, p2, p3) {
    const u = 1 - t;
    return u * u * u * p0 + 3 * u * u * t * p1 + 3 * u * t * t * p2 + t * t * t * p3;
  }

  function drawEye(o) {
    const { up, lo } = lidCurves(o);
    const upper = `M${-W} 0C${-W * 0.45} ${up} ${W * 0.45} ${up} ${W} 0`;
    const lower = `C${W * 0.45} ${lo} ${-W * 0.45} ${lo} ${-W} 0Z`;
    clipPathEl.setAttribute('d', upper + lower);
    outlineEl.setAttribute('d', upper);
    lowerEl.setAttribute('d', `M${W} 0` + lower.replace('Z', ''));
    const cu = up - 14 - 10 * o;
    creaseEl.setAttribute('d', `M${-W * 0.85} ${-6 - 6 * o}C${-W * 0.4} ${cu} ${W * 0.4} ${cu} ${W * 0.85} ${-6 - 6 * o}`);
    // 睫毛：睁眼时向上，闭眼时垂下
    const dirY = -0.9 + 1.9 * Math.min(1, Math.max(0, (o - 0.05) / 0.35));
    let d = '';
    for (let i = 1; i < 18; i++) {
      const t = i / 18;
      const x = bez(t, -W, -W * 0.45, W * 0.45, W), y = bez(t, 0, up, up, 0);
      const len = 8 + 16 * Math.sin(Math.PI * t);
      const lean = (t - 0.5) * 1.4;
      d += `M${x.toFixed(1)} ${y.toFixed(1)}l${(lean * len * 0.6).toFixed(1)} ${(-len * dirY).toFixed(1)}`;
    }
    lashesEl.setAttribute('d', d);
  }

  function drawIris() {
    const maxX = W * 0.5, maxY = Math.max(4, H * 0.5);
    const x = Math.max(-maxX, Math.min(maxX, E.ix + E.sacX));
    const y = Math.max(-maxY, Math.min(maxY, E.iy + E.sacY));
    irisEl.setAttribute('transform', `translate(${x.toFixed(2)} ${y.toFixed(2)})`);
    const base = 17 * E.dil;
    pupilEl.setAttribute('rx', (base * (1 - E.slit * 0.78)).toFixed(2));
    pupilEl.setAttribute('ry', (base * (1 + E.slit * 0.55)).toFixed(2));
    if (medalIris) medalIris.setAttribute('transform', `translate(${(x / W * 6).toFixed(2)} ${(y / H * 3).toFixed(2)})`);
  }

  // ---------- 全知之眼：位置 ----------
  function eyeSize() {
    const v = Math.min(innerWidth, innerHeight);
    return Math.max(190, Math.min(380, v * 0.34));
  }

  function placeEye() {
    const a = ACTS[Math.max(0, actIdx)];
    const size = eyeSize();
    eyeWrap.style.setProperty('--eye-size', size + 'px');
    const fr = frame.getBoundingClientRect();
    let x, y, s = a.eye.scale;
    if (E.staring) {
      x = fr.left + fr.width / 2; y = fr.top + fr.height * 0.4;
      s = Math.min(2.6, (fr.width * 0.95) / size);
    } else if (innerWidth <= 760) {
      // 窄屏：画框占满宽度，眼睛改为在画框上方从左到右移动
      const ang = a.eye.angle * Math.PI / 180;
      s = Math.min(s, 1.15);
      const m = size * s * 0.32;
      x = innerWidth / 2 + Math.cos(ang) * (innerWidth / 2 - m);
      y = Math.max(m * 0.8, fr.top - size * s * 0.16);
    } else {
      const ang = a.eye.angle * Math.PI / 180;
      const rx = fr.width / 2 + size * s * 0.3;
      const ry = fr.height / 2 + size * s * 0.22;
      x = fr.left + fr.width / 2 + Math.cos(ang) * rx;
      y = fr.top + fr.height / 2 + Math.sin(ang) * ry;
      const m = size * s * 0.3;
      x = Math.max(m, Math.min(innerWidth - m, x));
      y = Math.max(m * 0.9, Math.min(innerHeight - m, y));
    }
    E.x = x; E.y = y; E.s = s;
    eyeWrap.style.transform = `translate(${(x - size / 2).toFixed(1)}px, ${(y - size / 2).toFixed(1)}px) scale(${s})`;
    $('.redflash').style.setProperty('--fx', (x / innerWidth * 100).toFixed(1) + '%');
    $('.redflash').style.setProperty('--fy', (y / innerHeight * 100).toFixed(1) + '%');
  }

  function applyEyeMood(a) {
    eyeWrap.style.setProperty('--i1', a.eye.i1);
    eyeWrap.style.setProperty('--i2', a.eye.i2);
    eyeWrap.style.setProperty('--veins', a.eye.veins);
    eyeWrap.style.setProperty('--glow', a.eye.tension);
    E.dilT = a.eye.dil;
    E.slitT = a.eye.slit;
    E.tension = a.eye.tension;
    document.documentElement.style.setProperty('--beat', (2.8 - a.eye.tension * 1.9).toFixed(2) + 's');
  }

  // 画面坐标 → 屏幕坐标（与 SVG 的 slice 裁切一致）
  function scenePoint(px, py) {
    const r = stage.getBoundingClientRect();
    const k = Math.max(r.width / 1600, r.height / 1000);
    return [r.left + (r.width - 1600 * k) / 2 + px * k, r.top + (r.height - 1000 * k) / 2 + py * k];
  }

  // ---------- 全知之眼：每帧 ----------
  let last = performance.now();
  function tick(now) {
    const dt = Math.min(0.05, (now - last) / 1000);
    last = now;

    // 睁合
    let target = E.oT;
    if (E.tempOpen !== null) {
      if (now < E.tempUntil) target = E.tempOpen; else E.tempOpen = null;
    }
    if (now < E.blinkUntil) target = 0;
    else if (started && E.oT > 0.2 && now > E.nextBlink && !E.staring) {
      E.blinkUntil = now + 150 + Math.random() * 90;
      E.nextBlink = now + 2800 + Math.random() * (6500 - E.tension * 3500);
    }
    const speed = target < E.o ? (now < E.blinkUntil ? 22 : 3.2) : 2.6;
    E.o += (target - E.o) * Math.min(1, dt * speed);
    if (E.o < 0.002) E.o = 0;
    drawEye(E.o);

    // 视线：鼠标 > 剧情焦点
    let gx, gy;
    if (E.staring) {
      gx = E.x; gy = E.y;
    } else if (now - E.mouseAt < 2600) {
      gx = E.mx; gy = E.my;
    } else {
      const a = ACTS[Math.max(0, actIdx)];
      [gx, gy] = scenePoint(a.focus[0], a.focus[1]);
    }
    const dx = gx - E.x, dy = gy - E.y;
    const dist = Math.hypot(dx, dy) || 1;
    const reach = Math.min(1, dist / 320);
    const txi = dx / dist * reach * W * 0.5;
    const tyi = dy / dist * reach * H * 0.5;
    E.ix += (txi - E.ix) * Math.min(1, dt * 7);
    E.iy += (tyi - E.iy) * Math.min(1, dt * 7);

    // 眼球的微跳：越紧张越频繁
    if (now > E.nextSac) {
      const amp = E.staring ? 1.2 : 3 + E.tension * 7;
      E.sacX = (Math.random() - 0.5) * amp;
      E.sacY = (Math.random() - 0.5) * amp * 0.6;
      E.nextSac = now + 220 + Math.random() * (1400 - E.tension * 900);
    }

    // 瞳孔
    const dT = E.tempDil !== null && now < E.tempUntil ? E.tempDil : E.dilT;
    E.dil += (dT - E.dil) * Math.min(1, dt * 2.5);
    E.slit += (E.slitT - E.slit) * Math.min(1, dt * 2);
    drawIris();

    // 颤抖
    if (!reduceMotion && E.tension > 0.45) {
      const t = (E.tension - 0.45) * 2.2;
      eyeInner.style.transform = `translate(${((Math.random() - 0.5) * t).toFixed(2)}px, ${((Math.random() - 0.5) * t).toFixed(2)}px)`;
    } else {
      eyeInner.style.transform = '';
    }

    requestAnimationFrame(tick);
  }

  function blink() { E.blinkUntil = performance.now() + 220; }

  // ---------- 剧情特效 ----------
  function runFx(list) {
    if (!list) return;
    const now = performance.now();
    for (const fx of list) {
      switch (fx) {
        case 'blink': setTimeout(blink, 350); break;
        case 'widen': E.tempOpen = 1.12; E.tempDil = 0.55; E.tempUntil = now + 2600; break;
        case 'narrow': E.tempOpen = 0.3; E.tempDil = 0.75; E.tempUntil = now + 3200; break;
        case 'shake': shake(); break;
        case 'redflash': flash(); break;
        case 'watchers': for (let i = 0; i < 5; i++) setTimeout(spawnWatcher, i * 260); break;
        case 'cosmos': case 'skyeye': case 'animeeye': currentScene && currentScene.classList.add('on'); break;
        case 'reflect': currentScene && currentScene.classList.add('reflect'); break;
        case 'msg': currentScene && currentScene.classList.add('msg'); break;
        case 'nomsg': currentScene && currentScene.classList.remove('msg'); break;
        case 'sleep': E.oT = 0; E.tension = 0.1; break;
        case 'wake':
          E.oT = 0.15;
          setTimeout(() => { if (ACTS[actIdx].num === '第七幕') E.oT = ACTS[actIdx].eye.open || 1; }, 1600);
          break;
        case 'stare': stare(); break;
      }
    }
  }

  function shake() {
    if (reduceMotion) return;
    document.body.classList.remove('shake');
    void document.body.offsetWidth;
    document.body.classList.add('shake');
    setTimeout(() => document.body.classList.remove('shake'), 650);
    Audio.thump();
  }
  function flash() {
    const el = $('.redflash');
    el.classList.remove('go'); void el.offsetWidth; el.classList.add('go');
  }

  function stare() {
    E.staring = true;
    document.body.classList.add('staring');
    E.oT = 1.05; E.slitT = 0.85; E.dilT = 0.9; E.tension = 1;
    eyeWrap.style.setProperty('--glow', 1);
    eyeWrap.style.setProperty('--veins', 1);
    placeEye();
    Audio.swell();
  }

  // ---------- 窥视者：黑暗中睁开的小眼睛 ----------
  const watchersEl = $('#watchers');
  function spawnWatcher() {
    if (!started || document.hidden) return;
    const fr = frame.getBoundingClientRect();
    let x, y, tries = 0;
    do {
      x = Math.random() * innerWidth; y = Math.random() * innerHeight;
      tries++;
    } while (tries < 20 && x > fr.left - 30 && x < fr.right + 30 && y > fr.top - 30 && y < fr.bottom + 30);
    const s = 0.5 + Math.random() * 0.9;
    const el = document.createElement('div');
    el.className = 'watcher';
    el.style.left = x + 'px'; el.style.top = y + 'px';
    el.style.transform = `scale(${s.toFixed(2)})`;
    el.innerHTML = `<svg viewBox="-36 -20 72 40"><g class="lid"><path d="M-34 0Q0 -30 34 0Q0 24 -34 0Z" fill="#e8d6c0"/>` +
      `<g class="w-iris"><circle r="10" fill="#9b111e"/><ellipse rx="2.6" ry="8" fill="#000"/></g>` +
      `<path d="M-34 0Q0 -30 34 0" fill="none" stroke="#120204" stroke-width="2.5"/></g></svg>`;
    watchersEl.appendChild(el);
    const iris = el.querySelector('.w-iris');
    const dx = (E.mouseAt > 0 ? E.mx : innerWidth / 2) - x, dy = (E.mouseAt > 0 ? E.my : innerHeight / 2) - y;
    const d = Math.hypot(dx, dy) || 1;
    iris.setAttribute('transform', `translate(${(dx / d * 14).toFixed(1)} ${(dy / d * 5).toFixed(1)})`);
    setTimeout(() => el.remove(), 4300);
  }
  function watcherLoop() {
    if (started && !E.staring && E.tension >= 0.45 && Math.random() < E.tension * 0.7) spawnWatcher();
    setTimeout(watcherLoop, 2200 + Math.random() * 3000);
  }

  // ---------- 年份滚动 ----------
  let shownYear = null, yearAnim = null;
  function setYear(y) {
    if (yearAnim) cancelAnimationFrame(yearAnim);
    if (y === null) {
      shownYear = null; hudYear.textContent = '∞'; bigYear.textContent = '∞';
      return;
    }
    const from = shownYear === null ? y - 12 : shownYear;
    const t0 = performance.now(), dur = Math.min(2600, 500 + Math.abs(y - from) * 60);
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      const v = Math.round(from + (y - from) * e);
      hudYear.textContent = v; bigYear.textContent = v;
      if (k < 1) yearAnim = requestAnimationFrame(step); else shownYear = y;
    };
    yearAnim = requestAnimationFrame(step);
  }

  // ---------- 对白 ----------
  function showLine(i) {
    const a = ACTS[actIdx];
    const L = a.lines[i];
    lineIdx = i;
    clearTimeout(autoTimer);
    const isIt = L.who === IT;
    whoEl.textContent = L.who || '';
    whoEl.classList.toggle('it', isIt);
    textEl.className = 'text' + (L.who ? '' : ' narr') + (isIt ? ' it' : '');
    dialog.classList.add('show');
    dialog.classList.remove('done');
    if (L.year) setYear(L.year);
    if (isIt) Audio.whisper();
    runFx(L.fx);
    typeText(L.t, isIt);
  }

  function typeText(t, glitch) {
    clearTimeout(typingTimer);
    fullText = t;
    textEl.textContent = '';
    typing = true;
    let k = 0;
    const speed = glitch ? 90 : 42;
    const step = () => {
      if (glitch) {
        const sp = document.createElement('span');
        sp.textContent = t[k];
        sp.style.animationDelay = (-Math.random()).toFixed(2) + 's';
        textEl.appendChild(sp);
      } else {
        textEl.textContent = t.slice(0, k + 1);
      }
      k++;
      if (k < t.length) typingTimer = setTimeout(step, speed);
      else finishTyping();
    };
    step();
  }

  function finishTyping() {
    clearTimeout(typingTimer);
    if (typing && textEl.textContent !== fullText) {
      if (textEl.classList.contains('it')) {
        textEl.innerHTML = '';
        for (const ch of fullText) {
          const sp = document.createElement('span');
          sp.textContent = ch;
          sp.style.animationDelay = (-Math.random()).toFixed(2) + 's';
          textEl.appendChild(sp);
        }
      } else textEl.textContent = fullText;
    }
    typing = false;
    dialog.classList.add('done');
    scheduleAuto();
  }

  function scheduleAuto() {
    clearTimeout(autoTimer);
    if (auto && !busy) autoTimer = setTimeout(next, 2300 + fullText.length * 55);
  }

  // ---------- 换幕 ----------
  function goAct(n, dir) {
    if (n < 0 || n >= ACTS.length || busy) return;
    busy = true;
    clearTimeout(autoTimer);
    clearTimeout(typingTimer);
    typing = false;
    const first = actIdx === -1;
    const prev = currentScene;
    actIdx = n; lineIdx = -1;
    const a = ACTS[n];
    seen.add(n);

    // 结束凝视状态（重播或回退时）
    if (E.staring && a.num !== '终幕') {
      E.staring = false;
      document.body.classList.remove('staring');
    }

    dialog.classList.remove('show', 'done');
    E.oT = 0;
    blink();

    const el = document.createElement('div');
    el.className = 'scene';
    el.innerHTML = a.scene();
    if (!first) el.classList.add(dir < 0 ? 'in-prev' : 'in-next');
    stage.appendChild(el);
    if (prev) {
      prev.classList.add(dir < 0 ? 'out-prev' : 'out-next');
      setTimeout(() => prev.remove(), 1300);
    }
    currentScene = el;

    card.querySelector('.num').textContent = a.num;
    card.querySelector('.name').textContent = a.title;
    card.querySelector('.yr').textContent = a.year ? `A.D. ${a.year}` : 'BEFORE TIME';
    card.classList.remove('go'); void card.offsetWidth; card.classList.add('go');

    hudAct.innerHTML = `<b>${a.num}</b>${a.title}`;
    plate.textContent = `${a.num} · ${a.title}`;
    setYear(a.year);
    updateTimeline();
    Audio.thump();

    // 闭眼 → 移动 → 睁眼：时间流动的节拍
    setTimeout(() => { applyEyeMood(a); placeEye(); }, first ? 0 : 450);
    setTimeout(() => { E.oT = a.eye.open; }, first ? 900 : 2300);
    setTimeout(() => {
      busy = false;
      showLine(0);
    }, first ? 1900 : 2500);
  }

  function next() {
    if (!started) return;
    if (ended) return;
    if (busy) return;
    if (typing) { finishTyping(); return; }
    const a = ACTS[actIdx];
    if (lineIdx < a.lines.length - 1) showLine(lineIdx + 1);
    else if (actIdx < ACTS.length - 1) goAct(actIdx + 1, 1);
    else finale();
  }

  function prevAct() {
    if (!started || busy || actIdx <= 0) return;
    ended = false;
    $('#ending').classList.add('hide');
    goAct(actIdx - 1, -1);
  }

  function finale() {
    ended = true;
    clearTimeout(autoTimer);
    setTimeout(() => {
      const g = $('#ending');
      g.classList.remove('hide');
      g.querySelector('button').focus();
    }, 1800);
  }

  function restart() {
    $('#ending').classList.add('hide');
    if (document.activeElement) document.activeElement.blur();
    ended = false;
    E.staring = false;
    document.body.classList.remove('staring');
    goAct(0, 1);
  }

  // ---------- 时间轴 ----------
  function buildTimeline() {
    ACTS.forEach((a, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.textContent = a.short;
      b.title = `${a.num} · ${a.title}${a.year ? ' · ' + a.year : ''}`;
      b.setAttribute('aria-label', b.title);
      b.addEventListener('click', (e) => {
        e.stopPropagation();
        if (!started || busy || i === actIdx) return;
        ended = false;
        $('#ending').classList.add('hide');
        goAct(i, i < actIdx ? -1 : 1);
      });
      timeline.appendChild(b);
    });
  }
  function updateTimeline() {
    [...timeline.children].forEach((b, i) => {
      b.classList.toggle('cur', i === actIdx);
      b.classList.toggle('seen', seen.has(i));
      b.setAttribute('aria-current', i === actIdx ? 'step' : 'false');
    });
  }

  // ---------- 声音：低频嗡鸣 + 心跳 + 低语 ----------
  const Audio = (() => {
    let ctx = null, master = null, on = false;
    function init() {
      if (ctx) return;
      const AC = window.AudioContext || window.webkitAudioContext;
      if (!AC) return;
      ctx = new AC();
      master = ctx.createGain();
      master.gain.value = 0;
      master.connect(ctx.destination);
      const lp = ctx.createBiquadFilter();
      lp.type = 'lowpass'; lp.frequency.value = 220; lp.Q.value = 6;
      lp.connect(master);
      [41.2, 41.7, 61.8].forEach((fq, i) => {
        const o = ctx.createOscillator();
        o.type = i === 2 ? 'sine' : 'sawtooth';
        o.frequency.value = fq;
        const g = ctx.createGain();
        g.gain.value = i === 2 ? 0.05 : 0.07;
        o.connect(g); g.connect(lp); o.start();
      });
      const lfo = ctx.createOscillator();
      lfo.frequency.value = 0.07;
      const lg = ctx.createGain(); lg.gain.value = 90;
      lfo.connect(lg); lg.connect(lp.frequency); lfo.start();
    }
    function setOn(v) {
      on = v;
      if (v) init();
      if (!ctx) return;
      if (ctx.state === 'suspended') ctx.resume();
      master.gain.cancelScheduledValues(ctx.currentTime);
      master.gain.setTargetAtTime(v ? 0.55 : 0, ctx.currentTime, 0.8);
    }
    function thump() {
      if (!on || !ctx) return;
      const t = ctx.currentTime;
      [0, 0.28].forEach((d, i) => {
        const o = ctx.createOscillator(), g = ctx.createGain();
        o.type = 'sine';
        o.frequency.setValueAtTime(70, t + d);
        o.frequency.exponentialRampToValueAtTime(34, t + d + 0.25);
        g.gain.setValueAtTime(0.0001, t + d);
        g.gain.exponentialRampToValueAtTime(i ? 0.5 : 0.8, t + d + 0.02);
        g.gain.exponentialRampToValueAtTime(0.0001, t + d + 0.35);
        o.connect(g); g.connect(ctx.destination);
        o.start(t + d); o.stop(t + d + 0.4);
      });
    }
    function noise(dur, freq, peak) {
      if (!on || !ctx) return;
      const t = ctx.currentTime;
      const buf = ctx.createBuffer(1, ctx.sampleRate * dur, ctx.sampleRate);
      const data = buf.getChannelData(0);
      for (let i = 0; i < data.length; i++) data[i] = Math.random() * 2 - 1;
      const src = ctx.createBufferSource(); src.buffer = buf;
      const bp = ctx.createBiquadFilter(); bp.type = 'bandpass'; bp.frequency.value = freq; bp.Q.value = 3;
      bp.frequency.setValueAtTime(freq, t);
      bp.frequency.linearRampToValueAtTime(freq * 0.5, t + dur);
      const g = ctx.createGain();
      g.gain.setValueAtTime(0.0001, t);
      g.gain.linearRampToValueAtTime(peak, t + dur * 0.4);
      g.gain.linearRampToValueAtTime(0.0001, t + dur);
      src.connect(bp); bp.connect(g); g.connect(ctx.destination);
      src.start(t);
    }
    return {
      setOn, thump,
      whisper: () => noise(1.6, 900, 0.25),
      swell: () => { noise(4, 300, 0.4); thump(); },
      get on() { return on; }
    };
  })();

  // ---------- 背景：飘散的余烬 ----------
  function dust() {
    const c = $('#dust'), g = c.getContext('2d');
    let w, h, ps = [];
    const resize = () => {
      w = c.width = innerWidth * devicePixelRatio;
      h = c.height = innerHeight * devicePixelRatio;
      ps = Array.from({ length: Math.round(innerWidth * innerHeight / 14000) }, () => ({
        x: Math.random() * w, y: Math.random() * h,
        r: (0.4 + Math.random() * 1.6) * devicePixelRatio,
        v: (0.08 + Math.random() * 0.35) * devicePixelRatio,
        a: Math.random() * Math.PI * 2,
        hue: Math.random() < 0.7 ? '255,90,70' : '241,215,154'
      }));
    };
    resize();
    addEventListener('resize', resize);
    const loop = () => {
      g.clearRect(0, 0, w, h);
      for (const p of ps) {
        p.y -= p.v * (1 + E.tension);
        p.a += 0.01;
        p.x += Math.sin(p.a) * 0.3;
        if (p.y < -10) { p.y = h + 10; p.x = Math.random() * w; }
        g.fillStyle = `rgba(${p.hue},${(0.25 + 0.35 * Math.sin(p.a * 2) ** 2).toFixed(2)})`;
        g.beginPath(); g.arc(p.x, p.y, p.r, 0, Math.PI * 2); g.fill();
      }
      requestAnimationFrame(loop);
    };
    if (!reduceMotion) loop();
  }

  // ---------- 背景法阵 ----------
  function sigil() {
    const glyphs = 'ᚠᚢᚦᚨᚱᚲᚷᚹᚺᚾᛁᛃᛇᛈᛉᛊᛏᛒᛖᛗᛚᛜᛞᛟ';
    const ring = (rad, n, size) => {
      let s = '';
      for (let i = 0; i < n; i++) {
        const a = i / n * Math.PI * 2;
        const x = Math.cos(a) * rad, y = Math.sin(a) * rad;
        s += `<text x="${x.toFixed(1)}" y="${y.toFixed(1)}" font-size="${size}" text-anchor="middle" dominant-baseline="middle" transform="rotate(${(a * 180 / Math.PI + 90).toFixed(1)} ${x.toFixed(1)} ${y.toFixed(1)})">${glyphs[(i * 7) % glyphs.length]}</text>`;
      }
      return s;
    };
    let hept = '';
    for (let i = 0; i < 7; i++) {
      const a = -Math.PI / 2 + i * 2 * Math.PI / 7 * 3;
      hept += (i ? 'L' : 'M') + (Math.cos(a) * 380).toFixed(1) + ' ' + (Math.sin(a) * 380).toFixed(1);
    }
    $('#sigil').innerHTML = `<svg viewBox="-500 -500 1000 1000" width="100%" height="100%">
      <g class="spin-a" fill="none" stroke="#c9a45c" stroke-width="1">
        <circle r="480"/><circle r="440" stroke-dasharray="3 9"/><circle r="380"/>
        <path d="${hept}Z"/>
        <g fill="#c9a45c" stroke="none">${ring(460, 64, 16)}</g>
      </g>
      <g class="spin-b" fill="none" stroke="#9b111e" stroke-width="1.2">
        <circle r="300"/><circle r="250" stroke-dasharray="40 10 4 10"/>
        <path d="M0 -300L260 150L-260 150Z"/><path d="M0 300L-260 -150L260 -150Z"/>
        <g fill="#9b111e" stroke="none">${ring(275, 40, 18)}</g>
      </g>
    </svg>`;
  }

  // ---------- 全知之眼：静态结构 ----------
  function buildEye() {
    const r = (() => { let s = 99; return () => (s = (s * 16807) % 2147483647) / 2147483647; })();
    let rays = '';
    for (let i = 0; i < 56; i++) {
      const a = i / 56 * Math.PI * 2, long = i % 2 === 0;
      const r1 = 168, r2 = long ? 258 : 214;
      rays += `<line x1="${(Math.cos(a) * r1).toFixed(1)}" y1="${(Math.sin(a) * r1).toFixed(1)}" x2="${(Math.cos(a) * r2).toFixed(1)}" y2="${(Math.sin(a) * r2).toFixed(1)}" stroke-width="${long ? 2.2 : 1.2}" opacity="${long ? 0.55 : 0.35}"/>`;
    }
    let veins = '';
    const vein = (x, y, ang, len, depth) => {
      if (depth <= 0 || len < 6) return;
      const x2 = x + Math.cos(ang) * len, y2 = y + Math.sin(ang) * len;
      const cx = (x + x2) / 2 + (r() - 0.5) * len * 0.5, cy = (y + y2) / 2 + (r() - 0.5) * len * 0.5;
      veins += `<path d="M${x.toFixed(1)} ${y.toFixed(1)}Q${cx.toFixed(1)} ${cy.toFixed(1)} ${x2.toFixed(1)} ${y2.toFixed(1)}" stroke-width="${(depth * 0.55).toFixed(2)}"/>`;
      vein(x2, y2, ang + (r() - 0.5) * 1.1, len * 0.72, depth - 1);
      if (r() < 0.6) vein(x2, y2, ang + (r() < 0.5 ? -1 : 1) * (0.5 + r() * 0.6), len * 0.6, depth - 1);
    };
    for (let i = 0; i < 4; i++) vein(-W, (r() - 0.5) * 20, (r() - 0.5) * 0.9, 34 + r() * 14, 4);
    for (let i = 0; i < 4; i++) vein(W, (r() - 0.5) * 20, Math.PI + (r() - 0.5) * 0.9, 34 + r() * 14, 4);
    for (let i = 0; i < 3; i++) vein((r() - 0.5) * 120, H * 0.9, -Math.PI / 2 + (r() - 0.5) * 0.8, 24 + r() * 10, 3);
    let fibers = '';
    for (let i = 0; i < 64; i++) {
      const a = i / 64 * Math.PI * 2 + r() * 0.05;
      const r1 = 15 + r() * 4, r2 = 36 + r() * 8;
      fibers += `<line x1="${(Math.cos(a) * r1).toFixed(1)}" y1="${(Math.sin(a) * r1).toFixed(1)}" x2="${(Math.cos(a) * r2).toFixed(1)}" y2="${(Math.sin(a) * r2).toFixed(1)}" stroke="${i % 3 ? '#1a0204' : '#fff2c0'}" opacity="${i % 3 ? 0.35 : 0.3}"/>`;
    }
    const glyphs = 'ᛟᛞᛜᛚᛗᛖᛒᛏᛊᛉᛈᛇᛃᛁᚾᚺᚹᚷᚲᚱᚨᚦᚢᚠ';
    const tri = [[0, -235], [215, 140], [-215, 140]];
    let runes = '';
    for (let e = 0; e < 3; e++) {
      const [x1, y1] = tri[e], [x2, y2] = tri[(e + 1) % 3];
      const ang = Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI;
      for (let k = 1; k < 12; k++) {
        const t = k / 12, x = x1 + (x2 - x1) * t, y = y1 + (y2 - y1) * t;
        // 符文向外偏移一点
        const nx = (y2 - y1), ny = -(x2 - x1), nl = Math.hypot(nx, ny);
        runes += `<text x="${(x + nx / nl * 16).toFixed(1)}" y="${(y + ny / nl * 16).toFixed(1)}" transform="rotate(${ang.toFixed(1)} ${(x + nx / nl * 16).toFixed(1)} ${(y + ny / nl * 16).toFixed(1)})" text-anchor="middle" dominant-baseline="middle">${glyphs[(e * 11 + k) % glyphs.length]}</text>`;
      }
    }
    $('#eye').innerHTML = `
<defs>
  <radialGradient id="eSclera" cx="0" cy="0" r="135" gradientUnits="userSpaceOnUse">
    <stop offset="0" stop-color="#f7ecd6"/><stop offset=".5" stop-color="#e6cdb0"/><stop offset=".8" stop-color="#a8634c"/><stop offset="1" stop-color="#3b0e10"/>
  </radialGradient>
  <radialGradient id="eIris" cx="0" cy="0" r="46" gradientUnits="userSpaceOnUse">
    <stop offset="0" style="stop-color:var(--i1)"/><stop offset=".45" style="stop-color:var(--i1)"/><stop offset=".85" style="stop-color:var(--i2)"/><stop offset="1" stop-color="#080002"/>
  </radialGradient>
  <linearGradient id="eShade" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#1a0004" stop-opacity=".85"/><stop offset=".42" stop-color="#1a0004" stop-opacity="0"/><stop offset=".85" stop-color="#1a0004" stop-opacity="0"/><stop offset="1" stop-color="#1a0004" stop-opacity=".4"/>
  </linearGradient>
  <linearGradient id="eGold" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0" stop-color="#fff0c0"/><stop offset=".5" stop-color="#c9a45c"/><stop offset="1" stop-color="#6b4a1a"/>
  </linearGradient>
  <radialGradient id="eHalo"><stop offset="0" stop-color="#ff3a2a" stop-opacity=".45"/><stop offset=".6" stop-color="#7a0a14" stop-opacity=".18"/><stop offset="1" stop-color="#7a0a14" stop-opacity="0"/></radialGradient>
  <clipPath id="eClip"><path id="eClipPath"/></clipPath>
  <filter id="eBlur" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="7"/></filter>
</defs>
<circle r="250" fill="url(#eHalo)"/>
<g class="rays" stroke="#e8c47a">${rays}</g>
<path d="M0 -235L215 140L-215 140Z" fill="none" stroke="#ffcf7a" stroke-width="10" opacity=".35" filter="url(#eBlur)"/>
<path d="M0 -235L215 140L-215 140Z" fill="rgba(20,4,6,.55)" stroke="url(#eGold)" stroke-width="4.5" stroke-linejoin="round"/>
<path d="M0 -205L189 122L-189 122Z" fill="none" stroke="#c9a45c" stroke-width="1" opacity=".6"/>
<g class="tri-runes" fill="#e8c47a" font-size="15" opacity=".85">${runes}</g>
<g transform="translate(0 18)">
  <g clip-path="url(#eClip)">
    <rect x="-140" y="-100" width="280" height="200" fill="url(#eSclera)"/>
    <g id="eVeins" stroke="#9b111e" fill="none" stroke-linecap="round">${veins}</g>
    <g id="eIrisG">
      <circle r="46" fill="url(#eIris)"/>
      <g stroke-width="1.2">${fibers}</g>
      <circle r="46" fill="none" stroke="#0e0003" stroke-width="5"/>
      <circle r="20" fill="none" style="stroke:var(--i1)" stroke-width="1.5" opacity=".55"/>
      <ellipse id="ePupil" rx="17" ry="17" fill="#030001"/>
      <ellipse cx="-15" cy="-17" rx="10" ry="6.5" fill="#fff" opacity=".85" transform="rotate(-25 -15 -17)"/>
      <circle cx="17" cy="15" r="3.2" fill="#fff" opacity=".55"/>
    </g>
    <rect x="-140" y="-100" width="280" height="200" fill="url(#eShade)"/>
  </g>
  <path id="eCrease" fill="none" stroke="#c9a45c" stroke-width="2" opacity=".55"/>
  <path id="eLower" fill="none" stroke="#2a0608" stroke-width="2.5"/>
  <path id="eOutline" fill="none" stroke="#0e0103" stroke-width="5.5" stroke-linecap="round"/>
  <path id="eLashes" fill="none" stroke="#0e0103" stroke-width="2.6" stroke-linecap="round"/>
  <path id="eTear" d="M-30 50 C -34 80 -26 110 -32 150 C -36 180 -28 210 -30 240" fill="none" stroke="#b0101c" stroke-width="5" stroke-linecap="round"/>
</g>`;
  }

  // ---------- 启动 ----------
  function start() {
    if (started) return;
    started = true;
    $('#gate').classList.add('hide');
    if (document.activeElement) document.activeElement.blur();
    Audio.setOn(true);
    $('#btnSound').setAttribute('aria-pressed', 'true');
    E.nextBlink = performance.now() + 4000;
    goAct(0, 1);
  }

  function bind() {
    $('#gate button').addEventListener('click', start);
    $('#ending button').addEventListener('click', restart);
    frame.addEventListener('click', next);
    $('#btnNext').addEventListener('click', (e) => {
      e.stopPropagation();
      if (!started || busy) return;
      if (actIdx < ACTS.length - 1) goAct(actIdx + 1, 1); else if (!ended) finale();
    });
    $('#btnPrev').addEventListener('click', (e) => { e.stopPropagation(); prevAct(); });
    $('#btnAuto').addEventListener('click', (e) => {
      e.stopPropagation();
      auto = !auto;
      e.currentTarget.setAttribute('aria-pressed', String(auto));
      if (auto && !typing && !busy) next();
    });
    $('#btnSound').addEventListener('click', (e) => {
      e.stopPropagation();
      Audio.setOn(!Audio.on);
      e.currentTarget.setAttribute('aria-pressed', String(Audio.on));
    });
    addEventListener('keydown', (e) => {
      if (!started) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); start(); }
        return;
      }
      if (e.target.closest && e.target.closest('button') && (e.key === 'Enter' || e.key === ' ')) return;
      if (e.key === ' ' || e.key === 'Enter' || e.key === 'ArrowRight' || e.key === 'ArrowDown') { e.preventDefault(); next(); }
      else if (e.key === 'ArrowLeft') prevAct();
      else if (e.key === 'a' || e.key === 'A') $('#btnAuto').click();
    });
    addEventListener('pointermove', (e) => {
      E.mx = e.clientX; E.my = e.clientY; E.mouseAt = performance.now();
    });
    addEventListener('resize', placeEye);
  }

  sigil();
  buildTimeline();
  bind();
  dust();
  // 开场前：眼睛在画框上方沉睡
  actIdx = -1;
  applyEyeMood(ACTS[0]);
  E.tension = 0.25;
  requestAnimationFrame(() => {
    actIdx = 0; placeEye(); actIdx = -1;
    eyeWrap.style.transition = 'none';
    requestAnimationFrame(() => { eyeWrap.style.transition = ''; });
  });
  E.oT = 0.04;
  requestAnimationFrame(tick);
  watcherLoop();
})();
