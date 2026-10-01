export const FOCUS_AREA_LABELS = {
  ASSISTIVE_TECH_DIGITAL_ACCESS: "Assistive Tech & Digital Access",
  ORIENTATION_MOBILITY: "Orientation & Mobility",
  COMMUNITY_IDENTITY_SOCIAL: "Community, Identity & Social Life",
  HEALTHCARE_VISION_DIAGNOSIS: "Healthcare & Vision Diagnosis",
  DAILY_LIVING_UNCATEGORIZED: "Daily Living",
};

export function labelFor(topic) {
  return topic.display_name || FOCUS_AREA_LABELS[topic.focus_area] || topic.focus_area;
}

export function urgencyBand(score) {
  if (score == null) return null;
  if (score >= 0.66) return { tier: "critical", label: "Critical" };
  if (score >= 0.4) return { tier: "elevated", label: "Elevated" };
  return { tier: "watching", label: "Watching" };
}

export function trendDisplay(trend) {
  const normalized = (trend ?? "").toLowerCase().replace(/[\s_]+/g, "-");
  switch (normalized) {
    case "rising":
      return { icon: "▲", text: "Rising" };
    case "falling":
      return { icon: "▼", text: "Falling" };
    case "steady":
      return { icon: "■", text: "Steady" };
    default:
      return { icon: "•", text: "Limited data" };
  }
}