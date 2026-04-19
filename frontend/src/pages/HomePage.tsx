import { ArrowRight, Bot, LibraryBig } from "lucide-react";
import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <section className="home-page">
      <div className="home-panel">
        <p className="eyebrow">首页入口</p>
        <h2>政务智能审查工作台</h2>
        <p className="home-description">
          以审核点库为核心，连接 AI 批量审核、结果沉淀与工作底稿编辑，服务政务与法律文本审查场景。
        </p>

        <div className="home-actions">
          <Link to="/audit-library" className="entry-card">
            <div className="entry-card__icon">
              <LibraryBig size={20} />
            </div>
            <div>
              <strong>创建审核点库</strong>
              <p>从制度、法规和处罚标准中提取并整理可复用的审核点。</p>
            </div>
            <ArrowRight size={16} />
          </Link>

          <Link to="/ai-review" className="entry-card entry-card--primary">
            <div className="entry-card__icon">
              <Bot size={20} />
            </div>
            <div>
              <strong>AI审核</strong>
              <p>基于审核点库对主审文件与相关附件开展项目级审查，生成工作底稿与结果清单。</p>
            </div>
            <ArrowRight size={16} />
          </Link>
        </div>
      </div>
    </section>
  );
}
