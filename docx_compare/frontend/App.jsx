import { useEffect, useRef, useState } from "react";


const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const CATEGORY_PRIORITY = {
  paragraph: 0,
  sentence: 1,
  segment: 2,
};


function buildApiUrl(path) {
  return `${API_BASE}${path}`;
}


function formatCategoryStat(summary, categoryId) {
  if (categoryId === "paragraph") {
    return summary.commonParagraphCount;
  }
  if (categoryId === "sentence") {
    return summary.commonSentenceCount;
  }
  return summary.commonSegmentCount;
}


function App() {
  const [firstFile, setFirstFile] = useState(null);
  const [secondFile, setSecondFile] = useState(null);
  const [reviewResult, setReviewResult] = useState(null);
  const [selectedMatchId, setSelectedMatchId] = useState(null);
  const [visibleCategories, setVisibleCategories] = useState({
    paragraph: true,
    sentence: true,
    segment: true,
  });
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  const visibleMatchLookup = {};
  const visibleMatches = reviewResult
    ? reviewResult.matches.filter((match) => {
        if (visibleCategories[match.category]) {
          visibleMatchLookup[match.id] = match;
          return true;
        }
        return false;
      })
    : [];

  useEffect(() => {
    if (selectedMatchId && !visibleMatchLookup[selectedMatchId]) {
      setSelectedMatchId(null);
    }
  }, [
    selectedMatchId,
    reviewResult,
    visibleCategories.paragraph,
    visibleCategories.sentence,
    visibleCategories.segment,
  ]);

async function requestReview(url, formData = null) {
    setLoading(true);
    setErrorMessage("");

    try {
      const response = await fetch(buildApiUrl(url), {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const payload = await response.json().catch(() => ({}));
        const detail =
          typeof payload.detail === "string"
            ? payload.detail
            : "\u8bf7\u68c0\u67e5\u6587\u4ef6\u683c\u5f0f\u6216\u540e\u7aef\u670d\u52a1\u72b6\u6001\u3002";
        throw new Error(
          `\u5ba1\u67e5\u5931\u8d25\uff08HTTP ${response.status}\uff09\uff1a${detail}`
        );
      }

      const payload = await response.json();
      setReviewResult(payload);
      setSelectedMatchId(payload.matches[0]?.id ?? null);
      setVisibleCategories({
        paragraph: true,
        sentence: true,
        segment: true,
      });
    } catch (error) {
      setErrorMessage(
        error.message ||
          "\u5ba1\u67e5\u5931\u8d25\uff1a\u8bf7\u786e\u8ba4 FastAPI \u670d\u52a1\u5df2\u542f\u52a8\u3002"
      );
    } finally {
      setLoading(false);
    }
  }

  async function handleReviewSubmit(event) {
    event.preventDefault();
    if (!firstFile || !secondFile) {
      setErrorMessage(
        "\u8bf7\u5148\u9009\u62e9\u4e24\u4efd DOCX \u6587\u4ef6\u3002"
      );
      return;
    }

    const formData = new FormData();
    formData.append("first_file", firstFile);
    formData.append("second_file", secondFile);
    await requestReview("/api/review", formData);
  }

  async function handleSampleReview() {
    await requestReview("/api/review/sample");
  }

  function toggleCategory(categoryId) {
    setVisibleCategories((current) => ({
      ...current,
      [categoryId]: !current[categoryId],
    }));
  }

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="hero">
        <div>
          <p className="eyebrow">
            {"FastAPI + React \u6587\u6863\u5ba1\u67e5\u53f0"}
          </p>
          <h1>DOCX Review Studio</h1>
          <p className="hero-copy">
            {
              "\u4e0a\u4f20\u4e24\u4efd Word \u6587\u6863\u540e\uff0c\u4e00\u952e\u5ba1\u67e5\u5e76\u81ea\u52a8\u9ad8\u4eae\u76f8\u540c\u90e8\u5206\u3002\u70b9\u51fb\u4efb\u610f\u4e00\u5904\u9ad8\u4eae\uff0c\u53e6\u4e00\u4efd\u6587\u6863\u4f1a\u540c\u6b65\u5b9a\u4f4d\u5230\u5bf9\u5e94\u5185\u5bb9\u3002"
            }
          </p>
        </div>

        <div className="hero-badge">
          <span>{"\u76f8\u540c\u6bb5\u843d"}</span>
          <span>{"\u76f8\u540c\u53e5\u5b50"}</span>
          <span>{"\u8fde\u7eed\u516c\u5171\u7247\u6bb5"}</span>
        </div>
      </header>

      <section className="control-deck">
        <form className="upload-card" onSubmit={handleReviewSubmit}>
          <div className="card-header">
            <div>
              <p className="card-kicker">{"\u4e0a\u4f20\u6587\u6863"}</p>
              <h2>{"\u51c6\u5907\u5ba1\u67e5\u6750\u6599"}</h2>
            </div>

            <button className="primary-button" type="submit" disabled={loading}>
              {loading
                ? "\u5ba1\u67e5\u4e2d..."
                : "\u4e00\u952e\u5ba1\u67e5"}
            </button>
          </div>

          <div className="upload-grid">
            <FilePicker
              title={"\u6587\u6863 A"}
              file={firstFile}
              onChange={setFirstFile}
            />
            <FilePicker
              title={"\u6587\u6863 B"}
              file={secondFile}
              onChange={setSecondFile}
            />
          </div>

          <div className="action-row">
            <button
              className="ghost-button"
              type="button"
              onClick={handleSampleReview}
              disabled={loading}
            >
              {"\u4f7f\u7528\u793a\u4f8b\u6587\u4ef6\u76f4\u63a5\u6f14\u793a"}
            </button>

            <p className="helper-text">
              {
                "\u5ba1\u67e5\u5b8c\u6210\u540e\u4f1a\u751f\u6210\u53cc\u680f\u5bf9\u7167\u89c6\u56fe\uff0c\u5e76\u53ef\u4e0b\u8f7d\u4e24\u4efd\u5e26\u9ad8\u4eae\u7684 Word \u5ba1\u67e5\u7a3f\u3002"
              }
            </p>
          </div>

          {errorMessage ? <p className="error-banner">{errorMessage}</p> : null}
        </form>

        <aside className="summary-card">
          <p className="card-kicker">{"\u5ba1\u67e5\u8bf4\u660e"}</p>
          <h2>{"\u9605\u8bfb\u4e0e\u8054\u52a8"}</h2>
          <p className="summary-copy">
            {
              "\u53f3\u4fa7\u4f1a\u5217\u51fa\u6240\u6709\u5339\u914d\u9879\u3002\u4f60\u53ef\u4ee5\u4ece\u5217\u8868\u9009\u4e2d\u4e00\u9879\uff0c\u4e5f\u53ef\u4ee5\u76f4\u63a5\u70b9\u51fb\u6587\u6863\u4e2d\u7684\u9ad8\u4eae\u7247\u6bb5\uff0c\u4e24\u4fa7\u4f1a\u81ea\u52a8\u8054\u52a8\u805a\u7126\u3002"
            }
          </p>

          <div className="legend-grid">
            <LegendChip color="#f5b700" label={"\u76f8\u540c\u6bb5\u843d"} />
            <LegendChip color="#12b5cb" label={"\u76f8\u540c\u53e5\u5b50"} />
            <LegendChip color="#ff7a59" label={"\u8fde\u7eed\u516c\u5171\u7247\u6bb5"} />
          </div>

          {reviewResult ? (
            <div className="download-panel">
              <div className="download-copy">
                <p>
                  {
                    "\u5ba1\u67e5\u5df2\u5b8c\u6210\uff0c\u53ef\u4e0b\u8f7d\u4e24\u4efd\u5e26\u9ad8\u4eae\u7684 Word \u5ba1\u67e5\u7a3f\u3002"
                  }
                </p>
              </div>

              <div className="download-actions">
                <a
                  className="download-button"
                  href={buildApiUrl(reviewResult.downloads.first)}
                  target="_blank"
                  rel="noreferrer"
                >
                  {"\u4e0b\u8f7d\u6587\u6863 A \u5ba1\u67e5\u7a3f"}
                </a>
                <a
                  className="download-button"
                  href={buildApiUrl(reviewResult.downloads.second)}
                  target="_blank"
                  rel="noreferrer"
                >
                  {"\u4e0b\u8f7d\u6587\u6863 B \u5ba1\u67e5\u7a3f"}
                </a>
              </div>
            </div>
          ) : null}
        </aside>
      </section>

      {reviewResult ? (
        <main className="workspace">
          <section className="workspace-main">
            <section className="stats-bar">
              {reviewResult.categories.map((category) => (
                <button
                  key={category.id}
                  className={`stat-chip ${
                    visibleCategories[category.id] ? "active" : ""
                  }`}
                  onClick={() => toggleCategory(category.id)}
                  type="button"
                  style={{ "--chip-color": category.color }}
                >
                  <span>{category.label}</span>
                  <strong>
                    {formatCategoryStat(reviewResult.summary, category.id)}
                  </strong>
                </button>
              ))}
            </section>

            <section className="document-grid">
              <DocumentColumn
                title={reviewResult.summary.firstFileName}
                documentData={reviewResult.documents.first}
                visibleMatchLookup={visibleMatchLookup}
                selectedMatchId={selectedMatchId}
                onSelectMatch={setSelectedMatchId}
              />
              <DocumentColumn
                title={reviewResult.summary.secondFileName}
                documentData={reviewResult.documents.second}
                visibleMatchLookup={visibleMatchLookup}
                selectedMatchId={selectedMatchId}
                onSelectMatch={setSelectedMatchId}
              />
            </section>
          </section>

          <aside className="match-sidebar">
            <div className="card-header compact">
              <div>
                <p className="card-kicker">{"\u5339\u914d\u6e05\u5355"}</p>
                <h2>{"\u53ef\u70b9\u51fb\u8054\u52a8"}</h2>
              </div>
              <span className="match-count">{visibleMatches.length}</span>
            </div>

            <div className="match-list">
              {visibleMatches.map((match) => (
                <button
                  key={match.id}
                  type="button"
                  className={`match-card ${
                    selectedMatchId === match.id ? "active" : ""
                  }`}
                  style={{ "--match-color": match.color }}
                  onClick={() => setSelectedMatchId(match.id)}
                >
                  <div className="match-meta">
                    <span className="match-label">{match.label}</span>
                    <span className="match-size">
                      {`${match.length} \u5b57\u7b26`}
                    </span>
                  </div>
                  <p className="match-preview">{match.text}</p>
                  <div className="match-foot">
                    <span>{`A \u4fa7 ${match.firstCount} \u5904`}</span>
                    <span>{`B \u4fa7 ${match.secondCount} \u5904`}</span>
                  </div>
                </button>
              ))}
            </div>
          </aside>
        </main>
      ) : (
        <section className="empty-state">
          <div className="empty-card">
            <p className="card-kicker">{"\u7b49\u5f85\u5ba1\u67e5"}</p>
            <h2>
              {
                "\u4e0a\u4f20\u4e24\u4efd DOCX\uff0c\u6216\u76f4\u63a5\u8f7d\u5165\u793a\u4f8b\u6587\u4ef6"
              }
            </h2>
            <p>
              {
                "\u5ba1\u67e5\u5b8c\u6210\u540e\uff0c\u8fd9\u91cc\u4f1a\u51fa\u73b0\u53cc\u680f\u5bf9\u7167\u89c6\u56fe\u3001\u5339\u914d\u6e05\u5355\uff0c\u4ee5\u53ca\u4e24\u4efd\u53ef\u4e0b\u8f7d\u7684\u9ad8\u4eae\u5ba1\u67e5\u7a3f\u3002"
              }
            </p>
          </div>
        </section>
      )}
    </div>
  );
}


function FilePicker({ title, file, onChange }) {
  return (
    <label className="file-picker">
      <span className="file-label">{title}</span>
      <span className="file-name">
        {file ? file.name : "\u9009\u62e9 .docx \u6587\u4ef6"}
      </span>
      <input
        type="file"
        accept=".docx"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
      />
    </label>
  );
}


function LegendChip({ color, label }) {
  return (
    <div className="legend-chip" style={{ "--legend-color": color }}>
      <span className="legend-dot" />
      <span>{label}</span>
    </div>
  );
}


function DocumentColumn({
  title,
  documentData,
  visibleMatchLookup,
  selectedMatchId,
  onSelectMatch,
}) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!selectedMatchId || !containerRef.current) {
      return;
    }

    const target = containerRef.current.querySelector(
      `[data-match-ids~="${selectedMatchId}"]`
    );
    if (target) {
      target.scrollIntoView({
        block: "center",
        behavior: "smooth",
      });
    }
  }, [selectedMatchId]);

  return (
    <article className="document-card">
      <div className="card-header compact">
        <div>
          <p className="card-kicker">{"\u6587\u6863\u89c6\u56fe"}</p>
          <h2>{title}</h2>
        </div>
        <span className="doc-count">{`${documentData.blockCount} \u6bb5`}</span>
      </div>

      <div className="document-scroll" ref={containerRef}>
        {documentData.blocks.map((block) => (
          <p className="doc-paragraph" key={block.id}>
            <span className="block-index">
              {String(block.index).padStart(2, "0")}
            </span>
            <span className="paragraph-text">
              {block.segments.map((segment, index) => {
                const visibleMatchIds = segment.matchIds.filter(
                  (matchId) => visibleMatchLookup[matchId]
                );
                const primaryVisibleMatchId = [...visibleMatchIds].sort(
                  (left, right) =>
                    CATEGORY_PRIORITY[visibleMatchLookup[left].category] -
                    CATEGORY_PRIORITY[visibleMatchLookup[right].category]
                )[0];
                const categories = primaryVisibleMatchId
                  ? segment.categories.filter((category) =>
                      visibleMatchIds.some(
                        (matchId) =>
                          visibleMatchLookup[matchId].category === category
                      )
                    )
                  : [];
                const isActive =
                  selectedMatchId && visibleMatchIds.includes(selectedMatchId);

                if (!primaryVisibleMatchId) {
                  return <span key={`${block.id}-${index}`}>{segment.text}</span>;
                }

                return (
                  <button
                    key={`${block.id}-${index}`}
                    className={`highlight-fragment ${isActive ? "active" : ""}`}
                    style={{
                      "--match-color":
                        visibleMatchLookup[primaryVisibleMatchId].color,
                    }}
                    type="button"
                    data-match-ids={visibleMatchIds.join(" ")}
                    data-category={categories[0]}
                    onClick={() => onSelectMatch(primaryVisibleMatchId)}
                    title={visibleMatchLookup[primaryVisibleMatchId].label}
                  >
                    {segment.text}
                  </button>
                );
              })}
            </span>
          </p>
        ))}
      </div>
    </article>
  );
}


export default App;
