export const CATEGORIES = [
  { key: "pothole", label: "Pothole", color: "orange" },
  { key: "streetlight", label: "Streetlight", color: "yellow" },
  { key: "fallen_tree", label: "Fallen tree", color: "green" },
  { key: "garbage", label: "Garbage", color: "brown" },
  { key: "waterlogging", label: "Waterlogging", color: "blue" },
  { key: "other", label: "Other", color: "grey" },
];

export const CATEGORY_BY_KEY = Object.fromEntries(
  CATEGORIES.map((category) => [category.key, category]),
);
