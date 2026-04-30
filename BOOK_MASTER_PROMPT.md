# Multi-Phase Book Creation Master Prompt (Condensed)

## Project Overview

```yaml
project:
  title: "Voice3D: Transforming Sound into 3D Sculptures"
  subtitle: "A hands-on guide to audio visualization with MFCC, PCA, and ML"
  platform: https://stivibe.iotok.org/p/project-mkol6l3k/
  source_code: ./birdsong/birdsong-app/
  target_pages: 150
  languages: [English, Korean]
  audience: "High school students (STEM interest)"
```

---

# PHASE 0: User Preferences

**Ask these questions before starting:**

| Category | Question | Options |
|----------|----------|---------|
| Structure | Book structure? | A) Chapter-based B) Tutorial-driven C) Hybrid |
| Style | Writing style? | A) Academic B) Practical C) Balanced |
| Math | Mathematics depth? | A) Conceptual B) Essential formulas C) Full derivations |
| Code | Programming depth? | A) No code B) Examples C) Full tutorials |
| Korean | Technical terms? | A) Full Korean B) English + Korean (푸리에 변환) C) English only |

---

# PHASE 1: Planning & Outline

## Chapter Structure (8 Chapters + Projects + Appendices)

**Part I: Foundations (Ch 1-3)**
- Ch1: The Hidden World of Sound - Why visualize sound
- Ch2: Sound as Numbers - Analog to digital, sampling
- Ch3: Frequency - Pitch, harmonics, Fourier intuition

**Part II: Feature Extraction (Ch 4-5)**
- Ch4: FFT and Spectrograms - Time-frequency analysis
- Ch5: MFCC - Mel scale, feature extraction

**Part III: Features to 3D (Ch 6-7)**
- Ch6: PCA - Dimensionality reduction (18D → 3D)
- Ch7: K-Means Clustering - Color mapping

**Part IV: Visualization (Ch 8)**
- Ch8: Building 3D Sound Sculptures - Three.js, animation

**Projects (5)**: Platform exploration, bird comparison, clustering analysis, recording, voice analysis

**Appendices**: Glossary, Math reference, Pipeline, Bird guide, Code reference

---

# PHASE 2: Chapter Drafting (English)

## Writing Guidelines

- **Tone**: Engaging, accessible for high school students
- **Structure**: Hook → Objectives → Content → Demo → Try It! → Summary → Exercises
- **Analogies**: Sound waves = pond ripples, FFT = prism, MFCC = fingerprint, PCA = best photo angle, K-Means = sorting balls

## Key Technical Content

**Audio Pipeline (7 Steps)**:
1. Audio Loading (44,100 Hz)
2. Framing (10ms, 2048 samples, Hann window)
3. FFT (time → frequency)
4. Mel Filterbank (40 filters)
5. DCT → 13 MFCC coefficients
6. PCA (18D → 3D)
7. K-Means (6 clusters)

**18D Feature Vector**: 13 MFCC + spectral centroid + bandwidth + rolloff + flatness + zero-crossing rate

**Output**: `./en/01-*.md` through `./en/08-*.md`, projects, appendices

---

# PHASE 3: Fact-Checking

Extract verifiable claims, verify with 2+ sources (academic papers, textbooks, official docs).

**Output**: `./review/FACT_CHECK_*.md`

---

# PHASE 4: Critical Review

Score chapters on: Technical Accuracy (25%), Pedagogy (30%), Engagement (20%), Platform Integration (15%), Accessibility (10%)

**Output**: `./review/CRITICAL_REVIEW_REPORT.md`

---

# PHASE 5: Revision

Apply fixes in priority order: critical → major → minor. Document all changes.

**Output**: `./en/[chapter]_REVISED.md`

---

# PHASE 6: Image Generation

Use **Playwright** for screenshots from https://stivibe.iotok.org/p/project-mkol6l3k/
Use **Gemini 2.0 Flash** for conceptual diagrams (waves, ear anatomy, high-dimensional spaces).

**Output**: `./en/images/*.png`

---

# PHASE 7: Korean Translation

## Glossary

| English | Korean | Rule |
|---------|--------|------|
| FFT | FFT (고속 푸리에 변환) | 영어 + 한국어 |
| MFCC | MFCC (멜 주파수 켑스트럼 계수) | 영어 + 한국어 |
| PCA | PCA (주성분 분석) | 영어 + 한국어 |
| K-Means | K-평균 | 한국어 |
| Sampling | 샘플링 | 영어 병기 |

**Rules**: Keep code in English, translate comments, use 존댓말 (formal)

**Output**: `./ko/` (mirror of en/), `./ko/GLOSSARY.md`

---

# PHASE 8: PDF Generation

```bash
# English
pandoc ./en/COMPLETE_BOOK_EN.md -o ./output/Voice3D_EN.pdf --pdf-engine=xelatex --toc -V geometry:margin=1in

# Korean (two-step)
pandoc ./ko/COMPLETE_BOOK_KO.md -o /tmp/book_korean.tex --standalone -V mainfont="Noto Serif CJK KR"
cd ./ko && xelatex /tmp/book_korean.tex && mv book_korean.pdf ../output/Voice3D_KO.pdf
```

**Output**: `./output/Voice3D_*_EN.pdf`, `./output/Voice3D_*_KO.pdf`

---

# Reference

- **Inspiration**: Lucio Arese's "Visual Birds" (lucioarese.net)
- **Audio Source**: Cornell Lab - Voices of Eastern Backyard Birds
- **Platform**: stivibe.iotok.org

## Algorithms

| Algorithm | Parameters |
|-----------|------------|
| FFT | 2048 samples |
| Mel Filterbank | 40 filters |
| DCT | 13 coefficients |
| PCA | 18D → 3D |
| K-Means | K=6 |

---

# Constraints

- Credit Lucio Arese appropriately
- Cite Cornell Lab for audio
- High school appropriate content
- No hallucinated claims
- Backup files before overwriting
