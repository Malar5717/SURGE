import { GROUP_COLORS, groupLabel } from "../categories.js";

export default function FilterChips({ groups, active, onToggle }) {
  return (
    <div className="chips">
      {groups.map((group) => {
        const on = active.has(group);
        return (
          <button
            key={group}
            type="button"
            className={`chip ${on ? "chip-on" : "chip-off"}`}
            aria-pressed={on}
            onClick={() => onToggle(group)}
          >
            <span
              className="chip-dot"
              style={{ background: GROUP_COLORS[group] ?? "grey" }}
            />
            {groupLabel(group)}
          </button>
        );
      })}
    </div>
  );
}
