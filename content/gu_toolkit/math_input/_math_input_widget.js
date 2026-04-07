const MATHLIVE_MODULE_URL = "https://esm.run/mathlive@0.109.0";
const MATHLIVE_FONTS_URL = "https://cdn.jsdelivr.net/npm/mathlive@0.109.0/fonts";
const BOOTSTRAP_KEY = "__gu_toolkit_mathlive_bootstrap_v2";

function getBootstrap() {
  if (!globalThis[BOOTSTRAP_KEY]) {
    globalThis[BOOTSTRAP_KEY] = {
      modulePromise: null,
      async ensureMathLive() {
        if (!this.modulePromise) {
          this.modulePromise = import(MATHLIVE_MODULE_URL).then(async (mathlive) => {
            const MathfieldElement = mathlive?.MathfieldElement;
            if (!MathfieldElement) {
              throw new Error("MathLive module did not expose MathfieldElement.");
            }

            MathfieldElement.fontsDirectory = MATHLIVE_FONTS_URL;
            MathfieldElement.soundsDirectory = null;
            MathfieldElement.plonkSound = null;

            await customElements.whenDefined("math-field");
            return { MathfieldElement };
          });
        }
        return this.modulePromise;
      },
    };
  }
  return globalThis[BOOTSTRAP_KEY];
}

function normalizeValue(value) {
  return typeof value === "string" ? value : "";
}

function setMathfieldValue(field, value) {
  const next = normalizeValue(value);
  if (field.value === next) {
    return;
  }

  if (typeof field.setValue === "function") {
    field.setValue(next, { silenceNotifications: true });
    return;
  }

  field.value = next;
}

export default async function () {
  const { MathfieldElement } = await getBootstrap().ensureMathLive();

  return {
    render({ model, el }) {
      el.classList.add("gu-math-input-root");
      el.replaceChildren();

      const field = new MathfieldElement();
      field.setAttribute("aria-label", "Math input");
      setMathfieldValue(field, model.get("value"));

      const handleInput = () => {
        const next = normalizeValue(field.value);
        if (model.get("value") === next) {
          return;
        }
        model.set("value", next);
        model.save_changes();
      };

      const handleModelChange = () => {
        setMathfieldValue(field, model.get("value"));
      };

      field.addEventListener("input", handleInput);
      if (typeof model.on === "function") {
        model.on("change:value", handleModelChange);
      }

      el.appendChild(field);

      return () => {
        field.removeEventListener("input", handleInput);
        if (typeof model.off === "function") {
          model.off("change:value", handleModelChange);
        }
      };
    },
  };
}
