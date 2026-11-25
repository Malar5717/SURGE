import { CATEGORIES } from "../categories.js";

export default function FilterChips({ active, onToggle }) {
  return (
    <div className="chips">
      {CATEGORIES.map((category) => {
        const on = active.has(category.key);
        return (
          <button
            key={category.key}
            type="button"
            className={`chip ${on ? "chip-on" : "chip-off"}`}
            aria-pressed={on}
            onClick={() => onToggle(category.key)}
          >
            <span className="chip-dot" style={{ background: category.color }} />
            {category.label}
          </button>
        );
      })}
    </div>
  );
}
