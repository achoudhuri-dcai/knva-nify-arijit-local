import { FontAwesomeIcon } from "@fortawesome/react-fontawesome";
import type { IconDefinition } from "@fortawesome/fontawesome-svg-core";

interface FaIconProps {
  icon: IconDefinition;
  size?: "xs" | "sm" | "lg" | "1x";
  className?: string;
}

export default function FaIcon({ icon, size = "sm", className }: FaIconProps) {
  return <FontAwesomeIcon icon={icon} size={size} className={className} />;
}
