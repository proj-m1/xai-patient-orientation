const { createApp } = Vue;

createApp({
  data() {
    return {
      ongletCourant: "evaluation", // 'evaluation' | 'comparaison' | 'benchmark'
      form: {
        age: "inconnu",
        temperature: "inconnu",
        duree_symptomes: "inconnu",
        douleur: "inconnu",
        difficulte_respiratoire: "inconnu",
        douleur_thoracique: "inconnu",
        perte_conscience: "inconnu",
        saignement_important: "inconnu",
        fatigue_importante: "inconnu",
        symptomes_legers: "inconnu"
      },
      casDisponibles: [],
      selectedCasIdx: null,
      resultat: null,
      benchmarkData: null,
      loading: false,
      extractionLoading: false,
      descriptionLibre: "",
      benchLoading: false
    };
  },
  mounted() {
    this.chargerListeCas();
  },
  methods: {
    async chargerListeCas() {
      try {
        const res = await fetch("/api/cas_test");
        if (res.ok) {
          this.casDisponibles = await res.json();
        }
      } catch (e) {
        console.warn("Impossible de charger les cas de test prédéfinis:", e);
      }
    },
      chargerCas(casObj, idx) {
      this.selectedCasIdx = idx;
      const base = {
        age: "inconnu",
        temperature: "inconnu",
        duree_symptomes: "inconnu",
        douleur: "inconnu",
        difficulte_respiratoire: "inconnu",
        douleur_thoracique: "inconnu",
        perte_conscience: "inconnu",
        saignement_important: "inconnu",
        fatigue_importante: "inconnu",
        symptomes_legers: "inconnu"
      };
      this.form = { ...base, ...casObj.faits };
      this.evaluer();
    },
      reinitialiser() {
      this.selectedCasIdx = null;
      this.resultat = null;
        this.form = {
        age: "inconnu",
        temperature: "inconnu",
        duree_symptomes: "inconnu",
        douleur: "inconnu",
        difficulte_respiratoire: "inconnu",
        douleur_thoracique: "inconnu",
        perte_conscience: "inconnu",
        saignement_important: "inconnu",
        fatigue_importante: "inconnu",
        symptomes_legers: "inconnu"
        };
      this.descriptionLibre = "";
    },
      async evaluer() {
      this.loading = true;
      try {
        const res = await fetch("/api/evaluer", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ faits: this.form })
        });
        if (res.ok) {
          this.resultat = await res.json();
        }
      } catch (e) {
        alert("Erreur lors de l'évaluation du cas.");
      } finally {
        this.loading = false;
      }
      },
      async extraireFaits() {
        if (!this.descriptionLibre.trim()) return;
        this.extractionLoading = true;
        try {
          const res = await fetch("/api/extraire-faits", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ description: this.descriptionLibre })
          });
          const data = await res.json();
          if (!res.ok) throw new Error(data.erreur || "Extraction indisponible");
          this.form = { ...this.form, ...data.faits };
          await this.evaluer();
        } catch (e) {
          alert(e.message + ". Vous pouvez saisir les faits manuellement.");
        } finally {
          this.extractionLoading = false;
        }
      },
    async chargerBenchmark() {
      this.ongletCourant = 'benchmark';
      if (this.benchmarkData) return;
      this.benchLoading = true;
      try {
        const res = await fetch("/api/benchmark");
        if (res.ok) {
          this.benchmarkData = await res.json();
        }
      } catch (e) {
        alert("Erreur lors du calcul du benchmark.");
      } finally {
        this.benchLoading = false;
      }
    },
    getVerdictClass(o) {
      if (!o) return "v-surv";
      if (o.includes("URGENTE")) return "v-urg";
      if (o.includes("PRIORITAIRE")) return "v-prio";
      if (o.includes("NORMALE")) return "v-norm";
      if (o.includes("DEMANDER") || o.includes("MANUELLE")) return "v-alt";
      return "v-surv";
    },
  }
}).mount("#app");
