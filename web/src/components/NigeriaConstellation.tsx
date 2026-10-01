/** Stylized Nigeria constellation for the home hero (illustrative geometry, not GIS). */

export function NigeriaConstellation() {
  return (
    <svg
      className="constellation"
      viewBox="0 0 800 640"
      role="img"
      aria-label="Abstract map of Nigeria with glowing evidence trails"
    >
      <defs>
        <radialGradient id="nl-glow" cx="50%" cy="45%" r="55%">
          <stop offset="0%" stopColor="currentColor" stopOpacity="0.22" />
          <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
        </radialGradient>
      </defs>
      <rect width="800" height="640" fill="url(#nl-glow)" style={{ color: "var(--accent)" }} />
      {/* Simplified land mass */}
      <path
        className="constellation__land"
        d="M210 120
           C260 70, 360 55, 455 78
           C520 95, 575 120, 620 170
           C670 235, 690 310, 675 380
           C655 470, 600 530, 520 560
           C430 595, 340 585, 275 540
           C210 490, 175 410, 165 330
           C155 250, 170 175, 210 120 Z"
      />
      {/* Money / evidence trails */}
      <path
        className="constellation__trail"
        d="M240 210 C300 190, 360 230, 410 210 C470 185, 520 240, 580 250"
      />
      <path
        className="constellation__trail constellation__trail--secondary"
        d="M260 360 C330 330, 390 390, 450 370 C520 345, 560 400, 620 390"
      />
      <path
        className="constellation__trail"
        d="M300 470 C360 450, 420 500, 490 485 C540 475, 570 510, 600 500"
      />
      {/* Nodes */}
      <circle className="constellation__halo" cx="410" cy="210" r="18" />
      <circle
        className="constellation__node constellation__node--accent"
        cx="410"
        cy="210"
        r="5.5"
      />
      <circle className="constellation__node" cx="240" cy="210" r="4" />
      <circle
        className="constellation__node constellation__node--accent"
        cx="580"
        cy="250"
        r="4.5"
      />
      <circle className="constellation__node" cx="260" cy="360" r="4" />
      <circle className="constellation__node constellation__node--accent" cx="450" cy="370" r="5" />
      <circle className="constellation__node" cx="620" cy="390" r="3.5" />
      <circle
        className="constellation__node constellation__node--accent"
        cx="490"
        cy="485"
        r="4.5"
      />
      <circle className="constellation__node" cx="300" cy="470" r="3.5" />
    </svg>
  );
}
