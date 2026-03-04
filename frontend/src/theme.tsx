import { extendTheme } from "@chakra-ui/react"

const disabledStyles = {
  _disabled: {
    bg: "ui.main",
    opacity: 0.72,
  },
}

const theme = extendTheme({
  config: {
    initialColorMode: "light",
    useSystemColorMode: false,
  },
  fonts: {
    heading: "'IBM Plex Sans', 'Segoe UI', Arial, sans-serif",
    body: "'IBM Plex Sans', 'Segoe UI', Arial, sans-serif",
  },
  radii: {
    sm: "4px",
    md: "6px",
    lg: "8px",
  },
  colors: {
    ui: {
      main: "#204470",
      secondary: "#EAF0F8",
      success: "#2E7D32",
      danger: "#C62828",
      warning: "#F59E0B",
      light: "#F3F6FB",
      dark: "#1B2533",
      darkSlate: "#2A3647",
      border: "#D6DEE8",
      muted: "#5F6F86",
      dim: "#8C99AD",
      text: "#1D2633",
      panel: "#FFFFFF",
    },
  },
  styles: {
    global: {
      body: (props: { colorMode: "light" | "dark" }) => ({
        bg:
          props.colorMode === "dark"
            ? "linear-gradient(180deg, #101826 0%, #0B1220 100%)"
            : "linear-gradient(180deg, #F5F8FD 0%, #EEF3FA 100%)",
        color: props.colorMode === "dark" ? "#E8EEF7" : "ui.text",
        minHeight: "100vh",
      }),
      "#root": {
        minHeight: "100vh",
      },
    },
  },
  components: {
    Button: {
      variants: {
        primary: {
          bg: "ui.main",
          color: "white",
          _hover: {
            bg: "#1A3960",
          },
          _disabled: {
            ...disabledStyles,
            _hover: {
              ...disabledStyles,
            },
          },
          borderRadius: "6px",
        },
        danger: {
          bg: "ui.danger",
          color: "white",
          _hover: {
            bg: "#A61E1E",
          },
          borderRadius: "6px",
        },
        subtle: (props: { colorMode: "light" | "dark" }) => ({
          bg:
            props.colorMode === "dark"
              ? "rgba(35, 58, 93, 0.85)"
              : "rgba(234,240,248,0.85)",
          color: props.colorMode === "dark" ? "#E8EEF7" : "ui.main",
          _hover: {
            bg: props.colorMode === "dark" ? "#2A4268" : "#DCE6F3",
          },
          borderRadius: "6px",
        }),
      },
      defaultProps: {
        variant: "primary",
      },
    },
    Input: {
      baseStyle: (props: { colorMode: "light" | "dark" }) => ({
        field: {
          bg: props.colorMode === "dark" ? "#0F1A2B" : "white",
          color: props.colorMode === "dark" ? "#E8EEF7" : "ui.text",
          borderColor: "ui.border",
          _placeholder: {
            color: props.colorMode === "dark" ? "#8FA3BE" : "ui.dim",
          },
        },
      }),
      defaultProps: {
        focusBorderColor: "ui.main",
      },
    },
    Select: {
      baseStyle: (props: { colorMode: "light" | "dark" }) => ({
        field: {
          bg: props.colorMode === "dark" ? "#0F1A2B" : "white",
          color: props.colorMode === "dark" ? "#E8EEF7" : "ui.text",
          borderColor: "ui.border",
        },
      }),
      defaultProps: {
        focusBorderColor: "ui.main",
      },
    },
    Textarea: {
      baseStyle: (props: { colorMode: "light" | "dark" }) => ({
        bg: props.colorMode === "dark" ? "#0F1A2B" : "white",
        color: props.colorMode === "dark" ? "#E8EEF7" : "ui.text",
        borderColor: "ui.border",
        _placeholder: {
          color: props.colorMode === "dark" ? "#8FA3BE" : "ui.dim",
        },
      }),
      defaultProps: {
        focusBorderColor: "ui.main",
      },
    },
    Table: {
      baseStyle: (props: { colorMode: "light" | "dark" }) => ({
        th: {
          bg: props.colorMode === "dark" ? "#1A2A42" : "#F4F7FC",
          color: props.colorMode === "dark" ? "#CFE0F7" : "ui.darkSlate",
          fontSize: "11px",
          textTransform: "uppercase",
          letterSpacing: "0.05em",
          borderColor: "ui.border",
        },
        td: {
          borderColor: "ui.border",
        },
      }),
    },
    Tabs: {
      variants: {
        enclosed: (props: { colorMode: "light" | "dark" }) => ({
          tab: {
            color: props.colorMode === "dark" ? "#C8D5E8" : "ui.darkSlate",
            bg: props.colorMode === "dark" ? "rgba(255,255,255,0.03)" : "transparent",
            _selected: {
              color: props.colorMode === "dark" ? "#EAF2FF" : "ui.main",
              borderColor: "ui.border",
              bg: props.colorMode === "dark" ? "#1A2A42" : "white",
            },
          },
        }),
        "enclosed-colored": (props: { colorMode: "light" | "dark" }) => ({
          tab: {
            color: props.colorMode === "dark" ? "#C8D5E8" : "ui.darkSlate",
            borderColor: "ui.border",
            _selected: {
              color: props.colorMode === "dark" ? "#EAF2FF" : "ui.main",
              borderColor: "ui.border",
              bg: props.colorMode === "dark" ? "#1A2A42" : "white",
            },
          },
        }),
      },
    },
  },
})

export default theme
