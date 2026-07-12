/**
 * CreatorAnchorNav：UP 主目录锚点导航组件。
 * 展示当前标签下所有 UP 主及其未看视频数，点击可滚动到对应区域。
 * 当前可见的 UP 主对应锚点自动高亮。
 */
import type { CreatorGroup } from "../hooks/useTags";

interface CreatorAnchorNavProps {
  groups: CreatorGroup[];
  activeCreatorId: number | null;
  onSelect: (creatorId: number) => void;
}

export default function CreatorAnchorNav({
  groups,
  activeCreatorId,
  onSelect,
}: CreatorAnchorNavProps) {
  if (groups.length === 0) return null;

  return (
    <nav className="creator-anchor-nav">
      <ul>
        {groups.map((group) => (
          <li
            key={group.creatorId}
            onClick={() => onSelect(group.creatorId)}
            className={`creator-anchor-item${
              activeCreatorId === group.creatorId
                ? " creator-anchor-item-active"
                : ""
            }`}
            title={group.creatorAlias ? `${group.creatorAlias}（${group.creatorName}）` : group.creatorName}
          >
            <span className="truncate">
              {group.creatorAlias ? `${group.creatorAlias}（${group.creatorName}）` : group.creatorName}
            </span>
            <span className="anchor-badge">{group.videos.length}</span>
          </li>
        ))}
      </ul>
    </nav>
  );
}
