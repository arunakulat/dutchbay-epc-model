// Render the draft Envision technical proposal to an editable .docx.
//
// Content comes from proposal.json, exported by build_envision_proposal.py, so the Word and PDF
// deliverables share one source of truth. The «GF»…«/GF» sentinel marks DRAFTED GAP-FILL and is
// rendered as red (C00000) character formatting — direct formatting, not a style, so Envision can
// clear it with the normal Word controls as each item is confirmed.

const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, WidthType, AlignmentType, BorderStyle, ShadingType,
  PageNumber, Header, Footer, TabStopType, LevelFormat, convertInchesToTwip,
} = require("docx");

const doc = JSON.parse(fs.readFileSync(process.argv[2] || "proposal.json", "utf8"));
const OUT = process.argv[3] || "proposal.docx";

const RED = "C00000";
const INK = "1A1A1A";
const SLATE = "123B5D";
const MUTED = "5A6472";
const RULE = "C9D2DA";
const BAND = "F2F5F7";
const REDBAND = "FBEFEF";

// A4 with 1" margins; content width = 8.27in - 2in ≈ 6.27in
const PAGE_W = convertInchesToTwip(6.27);

// ── Sentinel → runs ──────────────────────────────────────────────────────────────────────
// Splits a string on the gap-fill sentinel and returns TextRun[] with red applied to the
// marked spans only. Any unterminated sentinel is surfaced rather than silently swallowed.
function runs(text, opts = {}) {
  const s = String(text == null ? "" : text);
  const out = [];
  let i = 0;
  while (i < s.length) {
    const open = s.indexOf("«GF»", i);
    if (open === -1) {
      if (i < s.length) out.push(new TextRun({ text: s.slice(i), ...opts }));
      break;
    }
    if (open > i) out.push(new TextRun({ text: s.slice(i, open), ...opts }));
    const close = s.indexOf("«/GF»", open);
    if (close === -1) {
      // Fail loud rather than emit a half-marked document.
      throw new Error(`unterminated gap-fill sentinel near: ${s.slice(open, open + 80)}`);
    }
    // opts FIRST: a caller-supplied base colour must not override the gap-fill red.
    out.push(new TextRun({ ...opts, text: s.slice(open + 4, close), color: RED }));
    i = close + 5;
  }
  return out.length ? out : [new TextRun({ text: "", ...opts })];
}

const P = (text, opts = {}) =>
  new Paragraph({
    children: runs(text, opts.run || {}),
    spacing: { after: opts.after == null ? 120 : opts.after, line: 276 },
    ...(opts.para || {}),
  });

function band(text, fill, borderColor) {
  return new Table({
    width: { size: PAGE_W, type: WidthType.DXA },
    columnWidths: [PAGE_W],
    borders: {
      top: { style: BorderStyle.NONE, size: 0, color: "auto" },
      bottom: { style: BorderStyle.NONE, size: 0, color: "auto" },
      right: { style: BorderStyle.NONE, size: 0, color: "auto" },
      insideHorizontal: { style: BorderStyle.NONE, size: 0, color: "auto" },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: "auto" },
      left: { style: BorderStyle.SINGLE, size: 18, color: borderColor },
    },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            width: { size: PAGE_W, type: WidthType.DXA },
            shading: { type: ShadingType.CLEAR, fill, color: "auto" },
            margins: { top: 140, bottom: 140, left: 180, right: 180 },
            children: [
              new Paragraph({
                children: runs(text, { size: 18, color: INK, bold: true }),
                spacing: { after: 0, line: 264 },
              }),
            ],
          }),
        ],
      }),
    ],
  });
}

function table(spec) {
  const cols = spec.columns || [];
  const n = cols.length || 1;
  // Give the first column less room where there are three, matching the PDF's proportions.
  let widths;
  if (n === 3) widths = [Math.round(PAGE_W * 0.2), Math.round(PAGE_W * 0.32), 0];
  else if (n === 2) widths = [Math.round(PAGE_W * 0.28), 0];
  else widths = Array(n).fill(Math.round(PAGE_W / n));
  widths[widths.length - 1] = PAGE_W - widths.slice(0, -1).reduce((a, b) => a + b, 0);

  const headerRow = new TableRow({
    tableHeader: true,
    children: cols.map((c, i) =>
      new TableCell({
        width: { size: widths[i], type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill: SLATE, color: "auto" },
        margins: { top: 90, bottom: 90, left: 120, right: 120 },
        children: [
          new Paragraph({
            children: [new TextRun({ text: String(c), bold: true, size: 17, color: "FFFFFF" })],
            spacing: { after: 0 },
          }),
        ],
      })
    ),
  });

  const bodyRows = [];
  (spec.rows || []).forEach((row, idx) => {
    if (row.group) {
      bodyRows.push(
        new TableRow({
          children: [
            new TableCell({
              columnSpan: n,
              width: { size: PAGE_W, type: WidthType.DXA },
              shading: { type: ShadingType.CLEAR, fill: "E4EAEF", color: "auto" },
              margins: { top: 80, bottom: 80, left: 120, right: 120 },
              children: [
                new Paragraph({
                  children: runs(row.group, { bold: true, size: 17, color: SLATE }),
                  spacing: { after: 0 },
                }),
              ],
            }),
          ],
        })
      );
      return;
    }
    const cells = row.cells || [];
    const fill = row.emphasis ? REDBAND : idx % 2 ? BAND : "FFFFFF";
    bodyRows.push(
      new TableRow({
        children: cells.map((cell, i) =>
          new TableCell({
            width: { size: widths[i], type: WidthType.DXA },
            shading: { type: ShadingType.CLEAR, fill, color: "auto" },
            margins: { top: 90, bottom: 90, left: 120, right: 120 },
            children: [
              new Paragraph({
                children: runs(cell, { size: 17, color: INK }),
                spacing: { after: 0, line: 264 },
              }),
            ],
          })
        ),
      })
    );
  });

  return new Table({
    width: { size: PAGE_W, type: WidthType.DXA },
    columnWidths: widths,
    borders: {
      top: { style: BorderStyle.SINGLE, size: 6, color: RULE },
      bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE },
      left: { style: BorderStyle.NONE, size: 0, color: "auto" },
      right: { style: BorderStyle.NONE, size: 0, color: "auto" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: RULE },
      insideVertical: { style: BorderStyle.NONE, size: 0, color: "auto" },
    },
    rows: [headerRow, ...bodyRows],
  });
}

// ── Body ─────────────────────────────────────────────────────────────────────────────────
const body = [];

body.push(
  new Paragraph({
    children: [new TextRun({ text: doc.title, bold: true, size: 40, color: SLATE })],
    heading: HeadingLevel.TITLE,
    spacing: { after: 80 },
  })
);
body.push(
  new Paragraph({
    children: [new TextRun({ text: doc.status, size: 20, color: RED, bold: true })],
    spacing: { after: 200 },
  })
);
body.push(band(doc.headline_caveat, REDBAND, RED));
body.push(P(""));
body.push(P(doc.disclaimer, { run: { size: 18, color: MUTED } }));
body.push(P(""));

body.push(
  new Paragraph({
    children: [new TextRun({ text: "0. Document control", bold: true, size: 26, color: SLATE })],
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 200, after: 140 },
  })
);
body.push(
  table({
    columns: ["Control field", "Controlled value"],
    rows: doc.control.map((kv) => ({ cells: [kv[0], kv[1]] })),
  })
);

doc.sections.forEach((sec, i) => {
  body.push(
    new Paragraph({
      children: [
        new TextRun({ text: `${i + doc.first_section_number}. ${sec.heading}`, bold: true, size: 26, color: SLATE }),
      ],
      heading: HeadingLevel.HEADING_1,
      spacing: { before: 320, after: 140 },
      pageBreakBefore: i === 0 ? false : false,
    })
  );
  body.push(band(sec.caveat || doc.section_caveat, BAND, SLATE));
  body.push(P(""));
  if (sec.intro) {
    body.push(P(sec.intro, { run: { size: 19, color: INK } }));
  }
  if (sec.table) {
    body.push(table(sec.table));
    (sec.table.notes || []).forEach((nt, k) =>
      body.push(P(`Note ${k + 1}. ${nt}`, { run: { size: 16, color: MUTED }, after: 60 }))
    );
    if (sec.table.source) {
      body.push(P(`Source: ${sec.table.source}`, { run: { size: 16, color: MUTED, italics: true } }));
    }
  }
  if (sec.points) {
    sec.points.forEach((pt) =>
      body.push(
        new Paragraph({
          children: runs(pt, { size: 19, color: INK }),
          numbering: { reference: "pts", level: 0 },
          spacing: { after: 140, line: 276 },
        })
      )
    );
  }
  if (sec.body) body.push(P(sec.body, { run: { size: 19, color: INK } }));
});

if (doc.provenance_lines && doc.provenance_lines.length) {
  body.push(
    new Paragraph({
      children: [new TextRun({ text: "Provenance", bold: true, size: 22, color: SLATE })],
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 320, after: 120 },
    })
  );
  doc.provenance_lines.forEach((l) => body.push(P(l, { run: { size: 16, color: MUTED }, after: 60 })));
}

// ── Document ─────────────────────────────────────────────────────────────────────────────
const out = new Document({
  creator: "DutchBay Technical Advisory",
  title: doc.title,
  description: "DRAFT FOR ENVISION COMPLETION — red text is drafted gap-fill, unverified.",
  numbering: {
    config: [
      {
        reference: "pts",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 360, hanging: 220 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: { page: { margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              children: [new TextRun({ text: doc.banner, size: 15, color: RED, bold: true })],
              spacing: { after: 60 },
              border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RULE, space: 6 } },
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              tabStops: [{ type: TabStopType.RIGHT, position: PAGE_W }],
              children: [
                new TextRun({
                  text: `${doc.document_id} | ${doc.version} | ${doc.issue_date} | ${doc.status}`,
                  size: 14,
                  color: MUTED,
                }),
                new TextRun({ text: "\t", size: 14 }),
                new TextRun({ text: "Page ", size: 14, color: MUTED }),
                new TextRun({ children: [PageNumber.CURRENT], size: 14, color: MUTED }),
                new TextRun({ text: " of ", size: 14, color: MUTED }),
                new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 14, color: MUTED }),
              ],
            }),
          ],
        }),
      },
      children: body,
    },
  ],
});

Packer.toBuffer(out).then((buf) => {
  fs.writeFileSync(OUT, buf);
  console.log(`wrote ${OUT} (${buf.length.toLocaleString()} bytes)`);
});
