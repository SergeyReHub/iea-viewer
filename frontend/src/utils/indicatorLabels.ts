export interface IndicatorLabelItem {
  fullLabel: string;
  shortLabel: string;
}

export interface IndicatorLabelGroup {
  commonLabel: string;
  commonSuffix: string;
  items: IndicatorLabelItem[];
}

export function splitIndicatorLabel(label: string): string[] {
  return label
    .split("|")
    .map((part) => part.trim())
    .filter(Boolean);
}

function commonPrefixLength(partsByLabel: string[][]): number {
  const segmentCount = Math.max(...partsByLabel.map((parts) => parts.length), 0);
  let length = 0;
  for (let index = 0; index < segmentCount; index += 1) {
    const values = new Set(partsByLabel.map((parts) => parts[index] ?? ""));
    if (values.size !== 1) {
      break;
    }
    length = index + 1;
  }
  return length;
}

function commonSuffixLength(partsByLabel: string[][], prefixLength: number): number {
  const segmentCount = Math.max(...partsByLabel.map((parts) => parts.length), 0);
  let length = 0;
  for (let offset = 1; offset <= segmentCount - prefixLength; offset += 1) {
    const values = new Set(partsByLabel.map((parts) => parts[parts.length - offset] ?? ""));
    if (values.size !== 1) {
      break;
    }
    length = offset;
  }
  return length;
}

export function buildIndicatorLabelGroups(labels: string[]): IndicatorLabelGroup[] {
  const uniqueLabels = Array.from(new Set(labels.map((label) => label.trim()).filter(Boolean)));
  if (!uniqueLabels.length) {
    return [];
  }
  if (uniqueLabels.length === 1) {
    const fullLabel = uniqueLabels[0];
    return [
      {
        commonLabel: "",
        commonSuffix: "",
        items: [{ fullLabel, shortLabel: fullLabel }]
      }
    ];
  }

  const partsByLabel = uniqueLabels.map((label) => splitIndicatorLabel(label));
  const prefixLength = commonPrefixLength(partsByLabel);
  const suffixLength = commonSuffixLength(partsByLabel, prefixLength);

  const commonLabel =
    prefixLength > 0 ? partsByLabel[0].slice(0, prefixLength).join(" | ") : "";
  const commonSuffix =
    suffixLength > 0
      ? partsByLabel[0].slice(partsByLabel[0].length - suffixLength).join(" | ")
      : "";

  const items = uniqueLabels.map((fullLabel, labelIndex) => {
    const parts = partsByLabel[labelIndex];
    const middleEnd = suffixLength > 0 ? parts.length - suffixLength : parts.length;
    const middle = parts.slice(prefixLength, middleEnd);
    const shortLabel = middle.join(" | ") || fullLabel;
    return { fullLabel, shortLabel };
  });

  const shouldGroup =
    (prefixLength > 0 || suffixLength > 0) &&
    items.some((item) => item.shortLabel.length < item.fullLabel.length);

  if (!shouldGroup) {
    return [
      {
        commonLabel: "",
        commonSuffix: "",
        items: uniqueLabels.map((fullLabel) => ({ fullLabel, shortLabel: fullLabel }))
      }
    ];
  }

  return [{ commonLabel, commonSuffix, items }];
}

export function mapIndicatorShortLabels(labels: string[]): Map<string, string> {
  const groups = buildIndicatorLabelGroups(labels);
  const mapping = new Map<string, string>();
  for (const group of groups) {
    for (const item of group.items) {
      mapping.set(item.fullLabel, item.shortLabel);
    }
  }
  return mapping;
}
