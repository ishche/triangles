/** Categorical colours for triangle and strut types; distinguishable on the light paper and dark background. */
export const PALETTE = [
  "#e0773c",
  "#3a7bd5",
  "#3fae7f",
  "#d8b23a",
  "#9c5fd0",
  "#d4506b",
  "#35b3c6",
  "#8a9b38",
  "#c77aa3",
  "#6b7fae",
  "#b8693a",
  "#58a858",
];

export const colorFor = (i: number) => PALETTE[i % PALETTE.length];
