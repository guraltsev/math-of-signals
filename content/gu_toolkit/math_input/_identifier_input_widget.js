const MATHLIVE_MODULE_URL = "https://esm.run/mathlive@0.109.0";
const MATHLIVE_FONTS_URL = "https://cdn.jsdelivr.net/npm/mathlive@0.109.0/fonts";
const BOOTSTRAP_KEY = "__gu_toolkit_mathlive_bootstrap_v2";
const CANONICAL_IDENTIFIER_PATTERN = /^[A-Za-z][A-Za-z0-9_]*$/;
const ATOM_TEXT_PATTERN = /^[A-Za-z0-9_]+$/;

const GREEK_NAME_TO_LATEX = Object.freeze({
  alpha: "\\alpha",
  beta: "\\beta",
  gamma: "\\gamma",
  delta: "\\delta",
  epsilon: "\\epsilon",
  varepsilon: "\\varepsilon",
  zeta: "\\zeta",
  eta: "\\eta",
  theta: "\\theta",
  vartheta: "\\vartheta",
  iota: "\\iota",
  kappa: "\\kappa",
  lambda: "\\lambda",
  mu: "\\mu",
  nu: "\\nu",
  xi: "\\xi",
  omicron: "o",
  pi: "\\pi",
  rho: "\\rho",
  sigma: "\\sigma",
  tau: "\\tau",
  upsilon: "\\upsilon",
  phi: "\\phi",
  varphi: "\\varphi",
  chi: "\\chi",
  psi: "\\psi",
  omega: "\\omega",
  Gamma: "\\Gamma",
  Delta: "\\Delta",
  Theta: "\\Theta",
  Lambda: "\\Lambda",
  Xi: "\\Xi",
  Pi: "\\Pi",
  Sigma: "\\Sigma",
  Upsilon: "\\Upsilon",
  Phi: "\\Phi",
  Psi: "\\Psi",
  Omega: "\\Omega",
});

const IDENTIFIER_LATEX_COMMANDS = Object.freeze({
  ...Object.fromEntries(Object.keys(GREEK_NAME_TO_LATEX).map((name) => [name, name])),
  sin: "sin",
  cos: "cos",
  tan: "tan",
  cot: "cot",
  sec: "sec",
  csc: "csc",
  sinh: "sinh",
  cosh: "cosh",
  tanh: "tanh",
  log: "log",
  ln: "ln",
  exp: "exp",
});

const GREEK_KEYBOARD_NAMES = Object.freeze([
  "alpha",
  "beta",
  "gamma",
  "delta",
  "epsilon",
  "varepsilon",
  "zeta",
  "eta",
  "theta",
  "vartheta",
  "iota",
  "kappa",
  "lambda",
  "mu",
  "nu",
  "xi",
  "pi",
  "rho",
  "sigma",
  "tau",
  "upsilon",
  "phi",
  "varphi",
  "chi",
  "psi",
  "omega",
  "Gamma",
  "Delta",
  "Theta",
  "Lambda",
  "Xi",
  "Pi",
  "Sigma",
  "Upsilon",
  "Phi",
  "Psi",
  "Omega",
]);

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

function normalizeString(value) {
  return typeof value === "string" ? value : "";
}

function normalizeContextNames(value) {
  return Array.isArray(value)
    ? value.filter((item) => typeof item === "string")
    : [];
}

function normalizeSymbolList(value) {
  return Array.isArray(value)
    ? value.filter((item) => typeof item === "string")
    : [];
}

function normalizePolicy(value) {
  return value === "context_or_new" ? "context_or_new" : "context_only";
}

function setMathfieldValue(field, value) {
  const next = normalizeString(value);
  if (field.value === next) {
    return;
  }

  if (typeof field.setValue === "function") {
    field.setValue(next, { silenceNotifications: true });
    return;
  }

  field.value = next;
}

function validateCanonicalIdentifier(name) {
  const text = normalizeString(name).trim();
  if (!CANONICAL_IDENTIFIER_PATTERN.test(text)) {
    throw new Error(`Identifier must match ${CANONICAL_IDENTIFIER_PATTERN}`);
  }
  splitIdentifierAtoms(text);
  return text;
}

function splitIdentifierAtoms(name) {
  const text = normalizeString(name).trim();
  if (!CANONICAL_IDENTIFIER_PATTERN.test(text)) {
    throw new Error(`Identifier must match ${CANONICAL_IDENTIFIER_PATTERN}`);
  }

  const atoms = [];
  let current = "";
  let index = 0;
  while (index < text.length) {
    const char = text[index];
    if (char !== "_") {
      current += char;
      index += 1;
      continue;
    }

    if (index + 1 < text.length && text[index + 1] === "_") {
      current += "_";
      index += 2;
      continue;
    }

    if (!current) {
      throw new Error(`Invalid identifier ${text}`);
    }
    atoms.push(current);
    current = "";
    index += 1;
  }

  if (!current) {
    throw new Error(`Invalid identifier ${text}`);
  }
  atoms.push(current);
  return atoms;
}

function encodeIdentifierAtoms(atoms) {
  const pieces = Array.from(atoms || []).map((atom) => normalizeString(atom).trim());
  if (pieces.length === 0 || pieces[0] === "") {
    throw new Error("Identifier must contain at least one atom.");
  }

  const encoded = pieces.map((atom, index) => {
    if (!atom) {
      throw new Error("Identifier cannot contain empty atoms.");
    }
    if (!ATOM_TEXT_PATTERN.test(atom)) {
      throw new Error(`Identifier atom ${atom} is invalid.`);
    }
    if (index === 0 && /^[0-9]/.test(atom)) {
      throw new Error(`Identifier must start with a letter, got ${atom}`);
    }
    return atom.replaceAll("_", "__");
  });

  return validateCanonicalIdentifier(encoded.join("_"));
}

function escapeMathTextAtom(atom) {
  return atom.replaceAll("_", "\\_");
}

function renderAtom(atom) {
  if (atom.includes("_")) {
    return `\\mathrm{${escapeMathTextAtom(atom)}}`;
  }
  if (Object.prototype.hasOwnProperty.call(GREEK_NAME_TO_LATEX, atom)) {
    return GREEK_NAME_TO_LATEX[atom];
  }
  if (/^[0-9]+$/.test(atom)) {
    return atom;
  }
  if (atom.length === 1) {
    return atom;
  }
  return `\\mathrm{${atom}}`;
}

function identifierToLatex(name) {
  const atoms = splitIdentifierAtoms(validateCanonicalIdentifier(name));
  const base = renderAtom(atoms[0]);
  if (atoms.length === 1) {
    return base;
  }
  const subscript = atoms.slice(1).map((atom) => renderAtom(atom)).join(",");
  return `${base}_{${subscript}}`;
}

function stripMathDelimiters(text) {
  const stripped = normalizeString(text).trim();
  if (stripped.length >= 2 && stripped[0] === "$" && stripped[stripped.length - 1] === "$") {
    return stripped.slice(1, -1).trim();
  }
  if (stripped.startsWith("\\(") && stripped.endsWith("\\)")) {
    return stripped.slice(2, -2).trim();
  }
  if (stripped.startsWith("\\[") && stripped.endsWith("\\]")) {
    return stripped.slice(2, -2).trim();
  }
  return stripped;
}

function skipSpaces(text, index) {
  let cursor = index;
  while (cursor < text.length && /\s/.test(text[cursor])) {
    cursor += 1;
  }
  return cursor;
}

function extractBracedGroup(text, start) {
  if (start >= text.length || text[start] !== "{") {
    throw new Error("Expected '{' while parsing LaTeX input.");
  }
  let depth = 0;
  for (let index = start; index < text.length; index += 1) {
    const char = text[index];
    if (char === "{") {
      depth += 1;
    } else if (char === "}") {
      depth -= 1;
      if (depth === 0) {
        return { group: text.slice(start + 1, index), end: index + 1 };
      }
    }
  }
  throw new Error("Unbalanced braces in LaTeX input.");
}

function decodeMathrmAtom(text) {
  const decoded = normalizeString(text).replaceAll("\\_", "_").trim();
  if (!decoded || !ATOM_TEXT_PATTERN.test(decoded)) {
    throw new Error(`Unsupported \\mathrm atom: ${text}`);
  }
  return decoded;
}

function parseDisplayAtom(text, start) {
  let index = skipSpaces(text, start);
  if (index >= text.length) {
    throw new Error("Expected identifier atom.");
  }

  if (text.startsWith("\\mathrm", index) || text.startsWith("\\operatorname", index)) {
    const command = text.startsWith("\\mathrm", index) ? "\\mathrm" : "\\operatorname";
    index += command.length;
    index = skipSpaces(text, index);
    const { group, end } = extractBracedGroup(text, index);
    return { atom: decodeMathrmAtom(group), end };
  }

  if (text[index] === "\\") {
    const commandMatch = /^\\([A-Za-z]+)/.exec(text.slice(index));
    if (!commandMatch) {
      throw new Error(`Unsupported LaTeX command near ${text.slice(index, index + 12)}`);
    }
    const command = commandMatch[1];
    if (!Object.prototype.hasOwnProperty.call(IDENTIFIER_LATEX_COMMANDS, command)) {
      throw new Error(`Unsupported identifier command \\${command}`);
    }
    return {
      atom: IDENTIFIER_LATEX_COMMANDS[command],
      end: index + commandMatch[0].length,
    };
  }

  const digitMatch = /^[0-9]+/.exec(text.slice(index));
  if (digitMatch) {
    return { atom: digitMatch[0], end: index + digitMatch[0].length };
  }

  const wordMatch = /^[A-Za-z][A-Za-z0-9]*/.exec(text.slice(index));
  if (wordMatch) {
    return { atom: wordMatch[0], end: index + wordMatch[0].length };
  }

  throw new Error(`Could not parse identifier atom near ${text.slice(index, index + 12)}`);
}

function parseDisplaySubscriptAtoms(text) {
  let index = 0;
  const atoms = [];
  while (true) {
    index = skipSpaces(text, index);
    const parsed = parseDisplayAtom(text, index);
    atoms.push(parsed.atom);
    index = skipSpaces(text, parsed.end);
    if (index >= text.length) {
      break;
    }
    if (text[index] !== ",") {
      throw new Error(`Expected ',' in identifier subscript list, got ${text[index]}`);
    }
    index += 1;
  }
  return atoms;
}

function parseDisplayIdentifier(text, start) {
  let index = skipSpaces(text, start);
  const base = parseDisplayAtom(text, index);
  const atoms = [base.atom];
  index = skipSpaces(text, base.end);

  if (index < text.length && text[index] === "_") {
    index += 1;
    index = skipSpaces(text, index);
    if (index < text.length && text[index] === "{") {
      const { group, end } = extractBracedGroup(text, index);
      atoms.push(...parseDisplaySubscriptAtoms(group));
      index = end;
    } else {
      const atom = parseDisplayAtom(text, index);
      atoms.push(atom.atom);
      index = atom.end;
    }
  }

  return { atoms, end: index };
}

function parseIdentifier(text) {
  const source = stripMathDelimiters(text).trim();
  if (!source) {
    throw new Error("Identifier is required.");
  }

  try {
    return validateCanonicalIdentifier(source);
  } catch {
    // Fall through to supported display-LaTeX parsing.
  }

  const parsed = parseDisplayIdentifier(source, 0);
  const index = skipSpaces(source, parsed.end);
  if (index !== source.length) {
    throw new Error(`Unexpected trailing text in identifier: ${source.slice(index)}`);
  }
  return encodeIdentifierAtoms(parsed.atoms);
}

function classifyIdentifierCandidate(candidate, contextNames, contextPolicy, forbiddenSymbols) {
  const text = normalizeString(candidate);

  if (text.trim() === "") {
    return {
      accepted: true,
      canonical: "",
      displayLatex: "",
      state: "empty",
    };
  }

  let canonical;
  try {
    canonical = parseIdentifier(text);
  } catch {
    return {
      accepted: false,
      canonical: "",
      displayLatex: text,
      state: "invalid-shape",
    };
  }

  if (forbiddenSymbols.includes(canonical)) {
    return {
      accepted: false,
      canonical,
      displayLatex: text,
      state: "forbidden",
    };
  }

  if (contextPolicy === "context_only" && !contextNames.includes(canonical)) {
    return {
      accepted: false,
      canonical,
      displayLatex: text,
      state: "not-in-context",
    };
  }

  return {
    accepted: true,
    canonical,
    displayLatex: identifierToLatex(canonical),
    state: contextNames.includes(canonical) ? "accepted-context" : "accepted-new",
  };
}

function updateRootState(root, classification, contextPolicy) {
  root.classList.toggle("hide-keyboard-toggle", contextPolicy !== "context_or_new");
  root.classList.toggle("is-empty", classification.state === "empty");
  root.classList.toggle(
    "is-accepted",
    classification.accepted && classification.state !== "empty",
  );
  root.classList.toggle("is-invalid", !classification.accepted);
  root.classList.toggle("is-forbidden", classification.state === "forbidden");
  root.dataset.validationState = classification.state;
}

function createEditMenuItem(field, id, label, command) {
  return {
    id,
    label,
    onMenuSelect: () => {
      field.executeCommand(command);
      field.focus();
    },
  };
}

function createInsertMenuItem(field, id, label, insertValue) {
  return {
    id,
    label,
    onMenuSelect: () => {
      field.executeCommand(["insert", insertValue]);
      field.focus();
    },
  };
}

function createContextMenuItem(name, onPick) {
  return {
    id: `context-name-${name}`,
    label: name,
    onMenuSelect: () => onPick(name),
  };
}

function createIdentifierMenu(field, contextNames, onPick, contextPolicy) {
  const menuItems = [];

  if (contextNames.length > 0) {
    menuItems.push({
      id: "context-names",
      label: "Context names",
      submenu: contextNames.map((name) => createContextMenuItem(name, onPick)),
    });
  }

  if (contextPolicy === "context_or_new") {
    if (menuItems.length > 0) {
      menuItems.push({ type: "divider" });
    }
    menuItems.push({
      id: "identifier-insert",
      label: "Insert",
      submenu: [createInsertMenuItem(field, "insert-subscript", "Subscript", "#@_{#?}")],
    });
  }

  if (menuItems.length > 0) {
    menuItems.push({ type: "divider" });
  }

  menuItems.push(
    createEditMenuItem(field, "undo", "Undo", "undo"),
    createEditMenuItem(field, "redo", "Redo", "redo"),
    { type: "divider" },
    createEditMenuItem(field, "cut", "Cut", "cutToClipboard"),
    createEditMenuItem(field, "copy", "Copy", "copyToClipboard"),
    createEditMenuItem(field, "paste", "Paste", "pasteFromClipboard"),
    { type: "divider" },
    createEditMenuItem(field, "select-all", "Select all", "selectAll"),
  );

  return menuItems;
}

function isMenuShortcut(event) {
  return event.code === "Space" || event.key === " " || event.key === "Spacebar";
}

function handleIdentifierKeydown(event) {
  const isBareAltShortcut = event.altKey && !event.ctrlKey && !event.metaKey;
  if (isBareAltShortcut && !isMenuShortcut(event)) {
    event.preventDefault();
    if (typeof event.stopImmediatePropagation === "function") {
      event.stopImmediatePropagation();
      return;
    }
    event.stopPropagation();
  }
}

async function appendAndWaitForMount(host, field) {
  let mounted = false;
  const mountPromise = new Promise((resolve) => {
    const handleMount = () => {
      mounted = true;
      resolve();
    };
    field.addEventListener("mount", handleMount, { once: true });
  });

  host.appendChild(field);

  await Promise.race([
    mountPromise,
    new Promise((resolve) => {
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          resolve();
        });
      });
    }),
  ]);

  if (!mounted) {
    await Promise.resolve();
  }
}

function applyIdentifierFieldConfiguration(field) {
  field.defaultMode = "math";
  field.inlineShortcuts = {};
  field.keybindings = Array.isArray(field.keybindings) ? [...field.keybindings] : [];
  field.mathVirtualKeyboardPolicy = "manual";
  field.popoverPolicy = "off";
  field.scriptDepth = [1, 0];
  field.smartFence = false;
  field.smartMode = false;
  field.smartSuperscript = false;
}

function getMathVirtualKeyboard() {
  return globalThis.mathVirtualKeyboard ?? null;
}

function chunk(items, size) {
  const rows = [];
  for (let index = 0; index < items.length; index += size) {
    rows.push(items.slice(index, index + size));
  }
  return rows;
}

function createLetterKeycap(letter) {
  return {
    latex: letter,
    shift: letter.toUpperCase(),
  };
}

function createContextKeycap(name) {
  return {
    label: name,
    insert: identifierToLatex(name),
    class: "small",
  };
}

function createGreekKeycap(name) {
  return {
    latex: identifierToLatex(name),
    aside: name,
  };
}

function createSubscriptKeycap() {
  return {
    label: "sub",
    insert: "#@_{#?}",
    class: "small",
  };
}

function createIdentifierKeyboardLayouts(contextNames, forbiddenSymbols) {
  const layouts = [];

  if (contextNames.length > 0) {
    const contextRows = chunk(contextNames.map((name) => createContextKeycap(name)), 4);
    contextRows.push(["[left]", "[right]", "[backspace]", "[hide-keyboard]"]);
    layouts.push({
      label: "ctx",
      tooltip: "Context names",
      rows: contextRows,
    });
  }

  layouts.push({
    label: "abc",
    tooltip: "Latin letters",
    rows: [
      [..."qwertyuiop"].map((letter) => createLetterKeycap(letter)),
      [..."asdfghjkl"].map((letter) => createLetterKeycap(letter)),
      [
        "[shift]",
        ...[..."zxcvbnm"].map((letter) => createLetterKeycap(letter)),
        createSubscriptKeycap(),
        "[backspace]",
      ],
      ["[undo]", "[redo]", "[left]", "[right]", "[hide-keyboard]"],
    ],
  });

  layouts.push({
    label: "123",
    tooltip: "Digits",
    rows: [
      ["[1]", "[2]", "[3]", "[4]", "[5]", "[6]", "[7]", "[8]", "[9]", "[0]"],
      [createSubscriptKeycap(), "[left]", "[right]", "[backspace]", "[hide-keyboard]"],
    ],
  });

  const greekNames = GREEK_KEYBOARD_NAMES.filter((name) => !forbiddenSymbols.includes(name));
  if (greekNames.length > 0) {
    const greekRows = chunk(greekNames.map((name) => createGreekKeycap(name)), 8);
    greekRows.push([createSubscriptKeycap(), "[left]", "[right]", "[backspace]", "[hide-keyboard]"]);
    layouts.push({
      label: "gr",
      tooltip: "Greek letters",
      rows: greekRows,
    });
  }

  return layouts;
}

export default async function () {
  const { MathfieldElement } = await getBootstrap().ensureMathLive();

  return {
    async render({ model, el }) {
      el.classList.add("gu-identifier-input-root");
      el.replaceChildren();

      let contextNames = normalizeContextNames(model.get("context_names"));
      let forbiddenSymbols = normalizeSymbolList(model.get("forbidden_symbols"));
      let contextPolicy = normalizePolicy(model.get("context_policy"));
      let committedCanonical = normalizeString(model.get("value"));

      const field = new MathfieldElement();
      field.setAttribute("aria-label", "Identifier input");
      await appendAndWaitForMount(el, field);
      applyIdentifierFieldConfiguration(field);
      setMathfieldValue(field, committedCanonical ? identifierToLatex(committedCanonical) : "");

      const refreshUi = (candidate) => {
        const classification = classifyIdentifierCandidate(
          candidate,
          contextNames,
          contextPolicy,
          forbiddenSymbols,
        );
        updateRootState(el, classification, contextPolicy);
        field.setAttribute("aria-invalid", classification.accepted ? "false" : "true");
        return classification;
      };

      const applyAcceptedCanonical = (canonicalName) => {
        committedCanonical = normalizeString(canonicalName);
        setMathfieldValue(field, committedCanonical ? identifierToLatex(committedCanonical) : "");
        const classification = refreshUi(field.value);
        if (classification.accepted && model.get("value") !== committedCanonical) {
          model.set("value", committedCanonical);
          model.save_changes();
        }
        field.focus();
      };

      const refreshMenu = () => {
        field.menuItems = createIdentifierMenu(
          field,
          contextNames,
          applyAcceptedCanonical,
          contextPolicy,
        );
      };

      const configureKeyboardLayouts = () => {
        const keyboard = getMathVirtualKeyboard();
        if (!keyboard) {
          return;
        }
        if (contextPolicy !== "context_or_new") {
          keyboard.layouts = "default";
          return;
        }
        keyboard.layouts = createIdentifierKeyboardLayouts(contextNames, forbiddenSymbols);
      };

      const hideKeyboardAndResetLayouts = () => {
        const keyboard = getMathVirtualKeyboard();
        if (!keyboard) {
          return;
        }
        if (typeof keyboard.hide === "function") {
          keyboard.hide();
        } else {
          keyboard.visible = false;
        }
        keyboard.layouts = "default";
      };

      const syncAcceptedValueFromField = ({ normalizeDisplay = false } = {}) => {
        const classification = refreshUi(field.value);
        if (!classification.accepted) {
          return classification;
        }

        committedCanonical = classification.canonical;
        if (normalizeDisplay) {
          setMathfieldValue(field, classification.displayLatex);
        }
        if (model.get("value") !== committedCanonical) {
          model.set("value", committedCanonical);
          model.save_changes();
        }
        return classification;
      };

      const handleModelValueChange = () => {
        const nextCanonical = normalizeString(model.get("value"));
        if (nextCanonical !== committedCanonical) {
          committedCanonical = nextCanonical;
          setMathfieldValue(
            field,
            committedCanonical ? identifierToLatex(committedCanonical) : "",
          );
        }
        refreshUi(field.value);
      };

      const handleContextNamesChange = () => {
        contextNames = normalizeContextNames(model.get("context_names"));
        refreshMenu();
        configureKeyboardLayouts();
        refreshUi(field.value);
      };

      const handleContextPolicyChange = () => {
        contextPolicy = normalizePolicy(model.get("context_policy"));
        refreshMenu();
        configureKeyboardLayouts();
        if (contextPolicy !== "context_or_new") {
          hideKeyboardAndResetLayouts();
        }
        refreshUi(field.value);
      };

      const handleForbiddenSymbolsChange = () => {
        forbiddenSymbols = normalizeSymbolList(model.get("forbidden_symbols"));
        configureKeyboardLayouts();
        refreshUi(field.value);
      };

      const handleFocusIn = () => {
        configureKeyboardLayouts();
      };

      const handleFocusOut = () => {
        syncAcceptedValueFromField({ normalizeDisplay: true });
        hideKeyboardAndResetLayouts();
      };

      field.addEventListener("input", () => {
        syncAcceptedValueFromField();
      });
      field.addEventListener("change", () => {
        syncAcceptedValueFromField({ normalizeDisplay: true });
      });
      field.addEventListener("focusin", handleFocusIn);
      field.addEventListener("focusout", handleFocusOut);
      field.addEventListener("keydown", handleIdentifierKeydown, true);
      if (typeof model.on === "function") {
        model.on("change:value", handleModelValueChange);
        model.on("change:context_names", handleContextNamesChange);
        model.on("change:context_policy", handleContextPolicyChange);
        model.on("change:forbidden_symbols", handleForbiddenSymbolsChange);
      }

      refreshMenu();
      configureKeyboardLayouts();
      refreshUi(field.value);

      return () => {
        field.removeEventListener("focusin", handleFocusIn);
        field.removeEventListener("focusout", handleFocusOut);
        field.removeEventListener("keydown", handleIdentifierKeydown, true);
        if (typeof model.off === "function") {
          model.off("change:value", handleModelValueChange);
          model.off("change:context_names", handleContextNamesChange);
          model.off("change:context_policy", handleContextPolicyChange);
          model.off("change:forbidden_symbols", handleForbiddenSymbolsChange);
        }
        hideKeyboardAndResetLayouts();
      };
    },
  };
}
