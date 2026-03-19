// src/utils/colorUtils.js

const predefinedColors = [
    '#FF0000', // Red
    '#0000FF', // Blue
    '#008000', // Green
    '#FFA500', // Orange
    '#FFFF00', // Yellow
    '#800080', // Purple
    '#00FFFF', // Cyan
    '#FFC0CB', // Pink
    '#A52A2A', // Brown
    '#808080', // Gray
  ];
  
  let colorIndex = 0;
  const colorMap = {};
  
  function getNextColor() {
    const color = predefinedColors[colorIndex % predefinedColors.length];
    colorIndex++;
    return color;
  }
  
  export function assignColorsToConcepts(concepts) {
    concepts.forEach((concept) => {
      if (!colorMap[concept]) {
        colorMap[concept] = getNextColor();
      }
    });
    return colorMap;
  }
  