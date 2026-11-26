export const GROUP_COLORS = {
  roads: "orange",
  water: "blue",
  power: "yellow",
  waste: "brown",
  animals: "purple",
  buildings: "teal",
  other: "grey",
  community_safety: "darkred",
};

export function groupLabel(slug) {
  const words = slug.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}
