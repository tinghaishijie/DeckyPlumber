import { FC } from "react";
import { SliderField, NotchLabel } from "@decky/ui";
import { useControllerMode } from "../../hooks/controller";
import { capitalize } from "lodash";
import { ControllerModes } from "../../backend/constants";

enum Mode {
  DEFAULT = 0,
  XBOX,
  XBOX_ELITE,
  DUAL_SENSE,
  DUAL_SENSE_EDGE,
  HORI_STEAM,
  STEAM_DECK,
  BITDO_ULTIMATE_2,
}

const ModeToKey: Record<ControllerModes, keyof typeof Mode> = {
  default: "DEFAULT",
  "xbox-series": "XBOX",
  "xbox-elite": "XBOX_ELITE",
  ds5: "DUAL_SENSE",
  "ds5-edge": "DUAL_SENSE_EDGE",
  "hori-steam": "HORI_STEAM",
  "deck-uhid": "STEAM_DECK",
  "8bitdo-u2": "BITDO_ULTIMATE_2",
};

const ControllerModeSlider: FC = () => {
  const [mode, setMode] = useControllerMode();

  const handleSliderChange = (value: number) => {
    const key = Mode[value] as
      | "DEFAULT"
      | "XBOX"
      | "XBOX_ELITE"
      | "DUAL_SENSE"
      | "DUAL_SENSE_EDGE"
      | "HORI_STEAM"
      | "STEAM_DECK"
      | "BITDO_ULTIMATE_2";

    return setMode(ControllerModes[key]);
  };

  const MODES: NotchLabel[] = Object.keys(Mode)
    .filter((key) => isNaN(Number(key)))
    .map((mode, idx) => {
      return {
        notchIndex: idx,
        label: capitalize(mode.split("_").join(" ")),
        value: idx,
      };
    });

  const sliderValue = Mode[ModeToKey[mode]];

  return (
    <>
      <SliderField
        value={sliderValue}
        min={0}
        max={MODES.length - 1}
        step={1}
        notchCount={MODES.length}
        notchLabels={MODES}
        notchTicksVisible={true}
        showValue={false}
        bottomSeparator={"none"}
        onChange={handleSliderChange}
      />
    </>
  );
};

export default ControllerModeSlider;
