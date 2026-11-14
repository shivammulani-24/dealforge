/**
 * GENERATED FILE — do not edit by hand.
 * Source: docs/openapi.json (committed; the backend CI checks it is current).
 * Regenerate with `npm run gen:api`; CI fails if this file is stale.
 */

export interface paths {
    "/api/v1/auth/logout": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Logout */
        post: operations["logout_api_v1_auth_logout_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/me": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Me */
        get: operations["me_api_v1_auth_me_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/register": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Register */
        post: operations["register_api_v1_auth_register_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/auth/token": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Token */
        post: operations["token_api_v1_auth_token_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/calculate/dcf": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Calculate Dcf
         * @description Stateless DCF: exactly the engine's result for exactly these inputs. Nothing is saved.
         */
        post: operations["calculate_dcf_api_v1_calculate_dcf_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/companies": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Companies */
        get: operations["list_companies_api_v1_companies_get"];
        put?: never;
        /** Create Company */
        post: operations["create_company_api_v1_companies_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/companies/{company_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Company */
        get: operations["get_company_api_v1_companies__company_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/companies/{company_id}/financials": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Financials */
        get: operations["get_financials_api_v1_companies__company_id__financials_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/companies/{company_id}/financials/import": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Import Financials */
        post: operations["import_financials_api_v1_companies__company_id__financials_import_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/companies/{company_id}/historical-analysis": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Historical Analysis */
        get: operations["get_historical_analysis_api_v1_companies__company_id__historical_analysis_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/companies/{company_id}/share-instruments": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Instruments */
        get: operations["get_instruments_api_v1_companies__company_id__share_instruments_get"];
        /** Put Instruments */
        put: operations["put_instruments_api_v1_companies__company_id__share_instruments_put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/dashboard": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Dashboard */
        get: operations["get_dashboard_api_v1_dashboard_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/health": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Health */
        get: operations["health_api_v1_health_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/line-items": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Line Item Dictionary */
        get: operations["line_item_dictionary_api_v1_line_items_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/line-items/{line_item_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        /** Patch Line Item */
        patch: operations["patch_line_item_api_v1_line_items__line_item_id__patch"];
        trace?: never;
    };
    "/api/v1/projects": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Projects */
        get: operations["list_projects_api_v1_projects_get"];
        put?: never;
        /** Create Project */
        post: operations["create_project_api_v1_projects_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{project_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Project */
        get: operations["get_project_api_v1_projects__project_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/projects/{project_id}/scenarios": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Scenarios */
        get: operations["list_scenarios_api_v1_projects__project_id__scenarios_get"];
        put?: never;
        /** Create Scenario */
        post: operations["create_scenario_api_v1_projects__project_id__scenarios_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /**
         * List All Runs
         * @description Every frozen run of the current user. Values are read verbatim from the stored results
         *     (never recomputed), so they are available whatever the current engine version (R1).
         */
        get: operations["list_all_runs_api_v1_runs_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Run */
        get: operations["get_run_api_v1_runs__run_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/sensitivity": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Run Sensitivity */
        post: operations["run_sensitivity_api_v1_runs__run_id__sensitivity_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/runs/{run_id}/verify": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Verify Run */
        post: operations["verify_run_api_v1_runs__run_id__verify_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/samples": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Samples */
        get: operations["list_samples_api_v1_samples_get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/samples/{sample_id}/load": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Load Sample */
        post: operations["load_sample_api_v1_samples__sample_id__load_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/scenarios/{scenario_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Scenario */
        get: operations["get_scenario_api_v1_scenarios__scenario_id__get"];
        /** Update Scenario */
        put: operations["update_scenario_api_v1_scenarios__scenario_id__put"];
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/scenarios/{scenario_id}/clone": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Clone Scenario */
        post: operations["clone_scenario_api_v1_scenarios__scenario_id__clone_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/scenarios/{scenario_id}/preview": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /**
         * Preview
         * @description Without a body: the saved scenario. With ``{settings, assumptions}``: an unsaved draft,
         *     validated like a save but never written (no rows, no audit event; D4-04).
         */
        post: operations["preview_api_v1_scenarios__scenario_id__preview_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/scenarios/{scenario_id}/runs": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** List Runs */
        get: operations["list_runs_api_v1_scenarios__scenario_id__runs_get"];
        put?: never;
        /** Create Run */
        post: operations["create_run_api_v1_scenarios__scenario_id__runs_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        get?: never;
        put?: never;
        /** Create Source */
        post: operations["create_source_api_v1_sources_post"];
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
    "/api/v1/sources/{source_id}": {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        /** Get Source */
        get: operations["get_source_api_v1_sources__source_id__get"];
        put?: never;
        post?: never;
        delete?: never;
        options?: never;
        head?: never;
        patch?: never;
        trace?: never;
    };
}
export type webhooks = Record<string, never>;
export interface components {
    schemas: {
        /** ActivityOut */
        ActivityOut: {
            /** Action */
            action: string;
            /** At */
            at: string;
            /** Company Id */
            company_id: number | null;
            /** Entity */
            entity: string;
            /** Entity Id */
            entity_id: number;
            /** Summary */
            summary: string;
        };
        /** AssumptionIn */
        AssumptionIn: {
            /**
             * Basis
             * @default assumed
             * @enum {string}
             */
            basis: "assumed" | "reported";
            /** Key */
            key: string;
            /** Rationale */
            rationale?: string | null;
            /** Source Id */
            source_id?: number | null;
            /** Value */
            value: number;
            /** Year Index */
            year_index: number | null;
        };
        /** AssumptionOut */
        AssumptionOut: {
            /**
             * Basis
             * @enum {string}
             */
            basis: "reported" | "assumed";
            /** Key */
            key: string;
            /** Rationale */
            rationale: string | null;
            /** Source Id */
            source_id: number | null;
            /** Value */
            value: number;
            /** Year Index */
            year_index: number | null;
        };
        /** AxisIn */
        AxisIn: {
            /** Step */
            step: number;
            /** Steps Each Side */
            steps_each_side: number;
            /**
             * Variable
             * @enum {string}
             */
            variable: "wacc" | "terminal_growth" | "revenue_growth_shift" | "ebitda_margin_shift" | "capex_pct_shift" | "tax_rate";
        };
        /** Body_import_financials_api_v1_companies__company_id__financials_import_post */
        Body_import_financials_api_v1_companies__company_id__financials_import_post: {
            /**
             * Basis
             * @enum {string}
             */
            basis: "reported" | "assumed";
            /** Currency */
            currency: string;
            /**
             * Dry Run
             * @default true
             */
            dry_run: boolean;
            /** File */
            file: string;
            /** Rationale */
            rationale?: string | null;
            /**
             * Replace
             * @default false
             */
            replace: boolean;
            /** Scale */
            scale: string;
        };
        /** BridgeInputsIn */
        BridgeInputsIn: {
            /** Cash */
            cash: number | null;
            /** Include Leases In Debt */
            include_leases_in_debt: boolean | null;
            /** Lease Liabilities */
            lease_liabilities: number | null;
            /** Non Controlling Interest */
            non_controlling_interest: number | null;
            /** Non Operating Assets */
            non_operating_assets: number | null;
            /** Other Debt Like Claims */
            other_debt_like_claims: number | null;
            /** Preferred Equity */
            preferred_equity: number | null;
            /** Total Debt */
            total_debt: number | null;
        };
        /** BridgeLine */
        BridgeLine: {
            /** Amount */
            amount: number;
            /** Label */
            label: string;
        };
        /** BridgeResult */
        BridgeResult: {
            /** Enterprise Value */
            enterprise_value: number;
            /** Equity Value */
            equity_value: number;
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /** Lines */
            lines: components["schemas"]["BridgeLine"][];
        };
        /** CloneIn */
        CloneIn: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "base" | "upside" | "downside" | "custom";
            /** Name */
            name: string;
        };
        /** CompanyIn */
        CompanyIn: {
            /** Currency */
            currency: string;
            /** Fiscal Year End Month */
            fiscal_year_end_month: number;
            /** Is Financial Institution */
            is_financial_institution: boolean;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Name */
            name: string;
            /**
             * Scale
             * @enum {string}
             */
            scale: "units" | "thousands" | "lakhs" | "millions" | "crores" | "billions";
            /** Sector */
            sector: string | null;
        };
        /** CompanyOut */
        CompanyOut: {
            /** Currency */
            currency: string;
            /** Fiscal Year End Month */
            fiscal_year_end_month: number;
            /** Id */
            id: number;
            /** Is Financial Institution */
            is_financial_institution: boolean;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Name */
            name: string;
            /** Scale */
            scale: string;
            /** Sector */
            sector: string | null;
        };
        /** CompanyRef */
        CompanyRef: {
            /** Currency */
            currency: string;
            /** Id */
            id: number;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Name */
            name: string;
            /** Scale */
            scale: string;
        };
        /** CompletenessGroupOut */
        CompletenessGroupOut: {
            /** Complete */
            complete: boolean;
            /** Missing */
            missing: string[];
            /** Required */
            required: string[];
        };
        /** CompletenessOut */
        CompletenessOut: {
            /** Absent */
            absent: number;
            /** Groups */
            groups: {
                [key: string]: components["schemas"]["CompletenessGroupOut"];
            };
            /** Missing */
            missing: number;
            /** Present */
            present: number;
        };
        /** ContextOut */
        ContextOut: {
            company: components["schemas"]["CompanyRef"];
            project: components["schemas"]["NamedRef"];
            scenario: components["schemas"]["NamedRef"];
        };
        /** ConvertibleInstrumentIn */
        ConvertibleInstrumentIn: {
            /** Conversion Price */
            conversion_price: number | null;
            /** Coupon Rate */
            coupon_rate: number | null;
            /** Face Value */
            face_value: number | null;
            /** Label */
            label: string;
        };
        /** CountsOut */
        CountsOut: {
            /** Companies */
            companies: number;
            /** Projects */
            projects: number;
            /** Runs */
            runs: number;
            /** Scenarios */
            scenarios: number;
        };
        /** DashboardCompanyOut */
        DashboardCompanyOut: {
            /** Fiscal Years */
            fiscal_years: number[];
            /** Id */
            id: number;
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Last Activity At */
            last_activity_at: string;
            /** Name */
            name: string;
        };
        /** DashboardOut */
        DashboardOut: {
            counts: components["schemas"]["CountsOut"];
            onboarding: components["schemas"]["OnboardingOut"];
            /** Recent Activity */
            recent_activity: components["schemas"]["ActivityOut"][];
            /** Recent Companies */
            recent_companies: components["schemas"]["DashboardCompanyOut"][];
            /** Recent Runs */
            recent_runs: components["schemas"]["DashboardRunOut"][];
        };
        /** DashboardRunOut */
        DashboardRunOut: {
            company: components["schemas"]["CompanyRef"];
            /** Created At */
            created_at: string;
            /** Engine Compatible */
            engine_compatible: boolean;
            /** Engine Version */
            engine_version: string;
            /** Id */
            id: number;
            /** Label */
            label: string | null;
            scenario: components["schemas"]["NamedRef"];
            /** Value Per Share */
            value_per_share: number;
        };
        /** DateSchedule */
        DateSchedule: {
            /** Convention */
            convention: string;
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /**
             * Market Data Date
             * Format: date
             */
            market_data_date: string;
            /** Market Data Gap Days */
            market_data_gap_days: number;
            /** Periods */
            periods: components["schemas"]["ForecastPeriod"][];
            /**
             * Statement Date
             * Format: date
             */
            statement_date: string;
            /**
             * Valuation Date
             * Format: date
             */
            valuation_date: string;
        };
        /** DcfInputsIn */
        DcfInputsIn: {
            bridge: components["schemas"]["BridgeInputsIn"];
            /** Current Share Price */
            current_share_price: number | null;
            dates: components["schemas"]["ValuationDatesIn"];
            forecast: components["schemas"]["ForecastInputsIn"];
            /** Is Financial Institution */
            is_financial_institution: boolean;
            /** Peer Ev Ebitda Range */
            peer_ev_ebitda_range: [
                number,
                number
            ] | null;
            share_capital: components["schemas"]["ShareCapitalInputsIn"];
            /** Tax Rate */
            tax_rate: number | null;
            /** Terminal Growth */
            terminal_growth: number | null;
            wacc_assumptions: components["schemas"]["WaccAssumptionsIn"] | null;
            /** Wacc Override */
            wacc_override: number | null;
        };
        /** DcfResult */
        DcfResult: {
            bridge: components["schemas"]["BridgeResult"];
            /** Current Share Price */
            current_share_price: number | null;
            /** Engine Version */
            engine_version: string;
            forecast: components["schemas"]["Forecast"];
            implied_exit_multiple: components["schemas"]["Metric"];
            /** Input Hash */
            input_hash: string;
            /** Issues */
            issues: components["schemas"]["Issue"][];
            per_share: components["schemas"]["ImpliedPerShare"];
            schedule: components["schemas"]["DateSchedule"];
            terminal: components["schemas"]["TerminalValue"];
            /** Ufcf */
            ufcf: components["schemas"]["UfcfLine"][];
            upside_vs_market: components["schemas"]["Metric"];
            valuation: components["schemas"]["EnterpriseValue"];
            /** Wacc */
            wacc: number;
            wacc_build: components["schemas"]["WaccResult"] | null;
        };
        /**
         * DebtValueBasis
         * @enum {string}
         */
        DebtValueBasis: "market" | "book";
        /** DerivedMetricOut */
        DerivedMetricOut: {
            /**
             * Basis
             * @constant
             */
            basis: "derived";
            /** Reason */
            reason: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "missing" | "not_meaningful";
            /** Value */
            value: number | null;
        };
        /** DilutionResult */
        DilutionResult: {
            /** Basic Shares */
            basic_shares: number;
            /** Converted Face */
            converted_face: number;
            /** Diluted Shares */
            diluted_shares: number;
            /** Lines */
            lines: components["schemas"]["InstrumentDilution"][];
            /** Method */
            method: string;
            /** Price */
            price: number;
            /** Unconverted Face */
            unconverted_face: number;
        };
        /** DiscountedFlow */
        DiscountedFlow: {
            /** Cash Flow */
            cash_flow: number;
            /** Discount Factor */
            discount_factor: number;
            /** Present Value */
            present_value: number;
            /** T */
            t: number;
        };
        /**
         * EbitdaBasis
         * @enum {string}
         */
        EbitdaBasis: "standardized" | "reported" | "adjusted";
        /** EbitdaReconciliation */
        EbitdaReconciliation: {
            adjusted: components["schemas"]["Metric"];
            adjustments_base: components["schemas"]["EbitdaBasis"] | null;
            /** Adjustments Total */
            adjustments_total: number | null;
            /** Issues */
            issues: components["schemas"]["Issue"][];
            reported: components["schemas"]["Metric"];
            standardized: components["schemas"]["Metric"];
        };
        /** EnterpriseValue */
        EnterpriseValue: {
            /** Enterprise Value */
            enterprise_value: number;
            /** Flows */
            flows: components["schemas"]["DiscountedFlow"][];
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /** Pv Terminal Value */
            pv_terminal_value: number;
            /** Sum Pv Flows */
            sum_pv_flows: number;
            /** Terminal Value */
            terminal_value: number;
            tv_share_of_ev: components["schemas"]["Metric"];
        };
        /** FinancialsOut */
        FinancialsOut: {
            /** Company Id */
            company_id: number;
            /** Currency */
            currency: string;
            /** Periods */
            periods: components["schemas"]["PeriodOut"][];
            /** Scale */
            scale: string;
        };
        /** Forecast */
        Forecast: {
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /** Years */
            years: components["schemas"]["ForecastYear"][];
        };
        /** ForecastInputsIn */
        ForecastInputsIn: {
            /** Base Nwc */
            base_nwc: number | null;
            /** Base Revenue */
            base_revenue: number | null;
            /** Years */
            years: components["schemas"]["ForecastYearDriversIn"][];
        };
        /** ForecastPeriod */
        ForecastPeriod: {
            /**
             * End Date
             * Format: date
             */
            end_date: string;
            /** Label */
            label: string;
            /** T */
            t: number;
        };
        /** ForecastYear */
        ForecastYear: {
            /** Capex */
            capex: number;
            /** Change In Nwc */
            change_in_nwc: number;
            /** Da */
            da: number;
            /** Ebit */
            ebit: number;
            /** Ebitda */
            ebitda: number;
            /** Nwc */
            nwc: number;
            /** Revenue */
            revenue: number;
            /** T */
            t: number;
        };
        /** ForecastYearDriversIn */
        ForecastYearDriversIn: {
            /** Capex Pct Revenue */
            capex_pct_revenue: number | null;
            /** Da Pct Revenue */
            da_pct_revenue: number | null;
            /** Ebitda Margin */
            ebitda_margin: number | null;
            /** Nwc Pct Revenue */
            nwc_pct_revenue: number | null;
            /** Revenue Growth */
            revenue_growth: number | null;
        };
        /** HTTPValidationError */
        HTTPValidationError: {
            /** Detail */
            detail?: components["schemas"]["ValidationError"][];
        };
        /** HealthOut */
        HealthOut: {
            /** Engine Version */
            engine_version: string;
            /**
             * Status
             * @constant
             */
            status: "ok";
        };
        /** HistoricalAnalysisOut */
        HistoricalAnalysisOut: {
            /** Issues */
            issues: components["schemas"]["IssueOut"][];
            /** Metric Definitions */
            metric_definitions: {
                [key: string]: components["schemas"]["MetricDefinitionOut"];
            };
            /** Periods */
            periods: components["schemas"]["PeriodAnalysisOut"][];
        };
        /** ImpliedPerShare */
        ImpliedPerShare: {
            /** Circular */
            circular: boolean;
            dilution: components["schemas"]["DilutionResult"];
            /** Equity Value Before Conversion */
            equity_value_before_conversion: number;
            /** Equity Value To Common */
            equity_value_to_common: number;
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /** Method */
            method: string;
            /** Value Per Share */
            value_per_share: number;
        };
        /** ImportIssueOut */
        ImportIssueOut: {
            /** Code */
            code: string;
            /** Column */
            column: string | null;
            /** Message */
            message: string;
            /** Row */
            row: number | null;
            /**
             * Severity
             * @enum {string}
             */
            severity: "error" | "warning" | "info";
        };
        /** ImportOut */
        ImportOut: {
            /** Committed */
            committed: boolean;
            /** Fiscal Years */
            fiscal_years?: number[] | null;
            preview: components["schemas"]["ImportPreviewOut"];
        };
        /** ImportPreviewOut */
        ImportPreviewOut: {
            /** Currency */
            currency: string;
            /** Errors */
            errors: components["schemas"]["ImportIssueOut"][];
            /** File Name */
            file_name: string;
            /** File Scale */
            file_scale: string;
            /** File Sha256 */
            file_sha256: string;
            /** Historical Metrics */
            historical_metrics: {
                [key: string]: unknown;
            }[] | null;
            /** Issues */
            issues: components["schemas"]["ImportIssueOut"][];
            /** Ok */
            ok: boolean;
            /** Periods */
            periods: components["schemas"]["ParsedPeriodOut"][];
            /** Stored Scale */
            stored_scale: string;
        };
        /** InstrumentDilution */
        InstrumentDilution: {
            /** Gross Shares */
            gross_shares: number;
            /** Included */
            included: boolean;
            kind: components["schemas"]["InstrumentKind"];
            /** Label */
            label: string;
            /** Net New Shares */
            net_new_shares: number;
            /** Note */
            note: string;
            /** Proceeds */
            proceeds: number;
            /** Shares Repurchased */
            shares_repurchased: number;
        };
        /** InstrumentIn */
        InstrumentIn: {
            /** Conversion Price */
            conversion_price?: number | null;
            /** Count */
            count?: number | null;
            /** Coupon Rate */
            coupon_rate?: number | null;
            /** Face Value */
            face_value?: number | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "option" | "warrant" | "rsu" | "convertible";
            /** Label */
            label: string;
            /** Strike */
            strike?: number | null;
        };
        /**
         * InstrumentKind
         * @enum {string}
         */
        InstrumentKind: "option" | "warrant" | "rsu" | "convertible";
        /** InstrumentOut */
        InstrumentOut: {
            /** Conversion Price */
            conversion_price: number | null;
            /** Count */
            count: number | null;
            /** Coupon Rate */
            coupon_rate: number | null;
            /** Face Value */
            face_value: number | null;
            /** Id */
            id: number;
            /**
             * Kind
             * @enum {string}
             */
            kind: "option" | "warrant" | "rsu" | "convertible";
            /** Label */
            label: string;
            /** Source Id */
            source_id: number;
            /** Strike */
            strike: number | null;
        };
        /** InstrumentsIn */
        InstrumentsIn: {
            /** Instruments */
            instruments: components["schemas"]["InstrumentIn"][];
            /** Source Ref */
            source_ref: string | null;
            /** Source Title */
            source_title: string;
        };
        /** InstrumentsPutOut */
        InstrumentsPutOut: {
            /** Company Id */
            company_id: number;
            /** Count */
            count: number;
            /** Source Id */
            source_id: number;
        };
        /** Issue */
        Issue: {
            /** Code */
            code: string;
            /** Field */
            field?: string | null;
            /** Message */
            message: string;
            severity: components["schemas"]["Severity"];
        };
        /** IssueOut */
        IssueOut: {
            /** Code */
            code: string;
            /** Field */
            field: string | null;
            /** Message */
            message: string;
            /**
             * Severity
             * @enum {string}
             */
            severity: "info" | "warning" | "error";
        };
        /** LineItemDefOut */
        LineItemDefOut: {
            /** Code */
            code: string;
            /** Label */
            label: string;
            /** Magnitude */
            magnitude: boolean;
            /** Statement */
            statement: string;
            /** Used By */
            used_by: string;
        };
        /** LineItemOut */
        LineItemOut: {
            /**
             * Basis
             * @enum {string}
             */
            basis: "reported" | "assumed" | "derived";
            /** Id */
            id: number;
            /** Item Code */
            item_code: string;
            /** Note */
            note: string | null;
            /** Original Scale */
            original_scale: string | null;
            /** Original Text */
            original_text: string | null;
            /** Original Value */
            original_value: number | null;
            /** Source Id */
            source_id: number;
            /** Source Ref */
            source_ref: string | null;
            /** Source Title */
            source_title: string;
            /** Value */
            value: number | null;
        };
        /**
         * LineItemPatchIn
         * @description C6 (breaking change): the basis is explicit. ``reported`` needs the source document;
         *     ``assumed`` needs a rationale. ``derived`` can't be entered (A6).
         */
        LineItemPatchIn: {
            /**
             * Basis
             * @enum {string}
             */
            basis: "reported" | "assumed";
            /** Rationale */
            rationale?: string | null;
            source?: components["schemas"]["SourceRefIn"] | null;
            /** Value */
            value: number | null;
        };
        /** LoginIn */
        LoginIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** Metric */
        Metric: {
            /** Reason */
            reason?: string | null;
            status: components["schemas"]["Status"];
            /** Value */
            value: number | null;
        };
        /** MetricDefinitionOut */
        MetricDefinitionOut: {
            /**
             * Basis
             * @constant
             */
            basis: "derived";
            /** Formula */
            formula: string;
            /** Items */
            items: string[];
            /** Not Meaningful */
            not_meaningful: string;
        };
        /** MetricOut */
        MetricOut: {
            /** Reason */
            reason: string | null;
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "missing" | "not_meaningful";
            /** Value */
            value: number | null;
        };
        /** NamedRef */
        NamedRef: {
            /** Id */
            id: number;
            /** Name */
            name: string;
        };
        /** OnboardingOut */
        OnboardingOut: {
            /** Complete */
            complete: boolean;
            /** Sample Available */
            sample_available: boolean;
            /** Sample Loaded */
            sample_loaded: boolean;
            /** Steps */
            steps: components["schemas"]["OnboardingStepOut"][];
        };
        /** OnboardingStepOut */
        OnboardingStepOut: {
            /** Done */
            done: boolean;
            /**
             * Key
             * @enum {string}
             */
            key: "company" | "statements" | "scenario" | "run";
            /** Label */
            label: string;
        };
        /** OptionTrancheIn */
        OptionTrancheIn: {
            /** Count */
            count: number | null;
            kind: components["schemas"]["InstrumentKind"];
            /** Label */
            label: string;
            /** Strike */
            strike: number | null;
        };
        /** ParsedCellOut */
        ParsedCellOut: {
            /** Column */
            column: string;
            /** Original Text */
            original_text: string;
            /** Original Value */
            original_value: number | null;
            /** Row */
            row: number;
            /** Value */
            value: number | null;
        };
        /** ParsedPeriodOut */
        ParsedPeriodOut: {
            /** Fiscal Year */
            fiscal_year: number;
            /** Period End */
            period_end: string;
            /** Values */
            values: {
                [key: string]: components["schemas"]["ParsedCellOut"];
            };
        };
        /** PatchLineItemOut */
        PatchLineItemOut: {
            /**
             * Basis
             * @enum {string}
             */
            basis: "reported" | "assumed" | "derived";
            /** Id */
            id: number;
            /** Item Code */
            item_code: string;
            /** Source Id */
            source_id: number;
            /** Value */
            value: number | null;
        };
        /** PeriodAnalysisOut */
        PeriodAnalysisOut: {
            ebitda: components["schemas"]["EbitdaReconciliation"];
            /** Fiscal Year */
            fiscal_year: number;
            /** Metrics */
            metrics: {
                [key: string]: components["schemas"]["DerivedMetricOut"];
            };
        };
        /** PeriodOut */
        PeriodOut: {
            completeness: components["schemas"]["CompletenessOut"];
            /** Fiscal Year */
            fiscal_year: number;
            /** Line Items */
            line_items: components["schemas"]["LineItemOut"][];
            /** Period End */
            period_end: string;
        };
        /** PresentationOut */
        PresentationOut: {
            /**
             * Basis
             * @constant
             */
            basis: "derived";
            /** Years */
            years: components["schemas"]["PresentationYearOut"][];
        };
        /** PresentationYearOut */
        PresentationYearOut: {
            ebit_margin: components["schemas"]["MetricOut"];
            /** T */
            t: number;
            ufcf_margin: components["schemas"]["MetricOut"];
        };
        /** PreviewOut */
        PreviewOut: {
            context: components["schemas"]["ContextOut"];
            /** Draft */
            draft: boolean;
            /** Engine Version */
            engine_version: string;
            /** Input Hash */
            input_hash: string;
            presentation: components["schemas"]["PresentationOut"];
            /** Provenance */
            provenance: {
                [key: string]: unknown;
            };
            result: components["schemas"]["DcfResult"];
            /**
             * Result Basis
             * @constant
             */
            result_basis: "derived";
            /** Warnings */
            warnings: components["schemas"]["IssueOut"][];
        };
        /** ProjectIn */
        ProjectIn: {
            /** Company Id */
            company_id: number;
            /** Description */
            description: string | null;
            /** Name */
            name: string;
        };
        /** ProjectOut */
        ProjectOut: {
            /** Company Id */
            company_id: number;
            /** Description */
            description: string | null;
            /** Id */
            id: number;
            /** Name */
            name: string;
        };
        /** RegisterIn */
        RegisterIn: {
            /** Email */
            email: string;
            /** Password */
            password: string;
        };
        /** RsuGrantIn */
        RsuGrantIn: {
            /** Count */
            count: number | null;
            /** Label */
            label: string;
        };
        /** RunIn */
        RunIn: {
            /** Label */
            label?: string | null;
        };
        /** RunOut */
        RunOut: {
            context: components["schemas"]["ContextOut"];
            /** Created At */
            created_at: string;
            /** Engine Compatible */
            engine_compatible: boolean;
            /** Engine Version */
            engine_version: string;
            /** Id */
            id: number;
            /** Input Hash */
            input_hash: string;
            /** Inputs */
            inputs: {
                [key: string]: unknown;
            };
            /** Label */
            label: string | null;
            presentation: components["schemas"]["PresentationOut"];
            /** Project Id */
            project_id: number;
            /** Provenance */
            provenance: {
                [key: string]: unknown;
            };
            result: components["schemas"]["DcfResult"];
            /**
             * Result Basis
             * @constant
             */
            result_basis: "derived";
            /** Scenario Id */
            scenario_id: number;
            /** Warnings */
            warnings: components["schemas"]["IssueOut"][];
        };
        /** RunsPageItemOut */
        RunsPageItemOut: {
            company: components["schemas"]["CompanyRef"];
            /** Created At */
            created_at: string;
            /** Engine Compatible */
            engine_compatible: boolean;
            /** Engine Version */
            engine_version: string;
            /** Enterprise Value */
            enterprise_value: number;
            /** Equity Value */
            equity_value: number;
            /** Id */
            id: number;
            /** Input Hash */
            input_hash: string;
            /** Label */
            label: string | null;
            project: components["schemas"]["NamedRef"];
            scenario: components["schemas"]["NamedRef"];
            /** Valuation Date */
            valuation_date: string;
            /** Value Per Share */
            value_per_share: number;
            /** Warning Count */
            warning_count: number;
        };
        /** RunsPageOut */
        RunsPageOut: {
            /** Items */
            items: components["schemas"]["RunsPageItemOut"][];
            /** Page */
            page: number;
            /** Page Size */
            page_size: number;
            /** Total */
            total: number;
        };
        /** SampleLoadOut */
        SampleLoadOut: {
            /** Company Id */
            company_id: number;
            /** Project Id */
            project_id: number;
            /** Scenario Id */
            scenario_id: number;
        };
        /** SampleOut */
        SampleOut: {
            /** Description */
            description: string;
            /** Id */
            id: string;
            /** Includes */
            includes: string[];
            /** Is Synthetic */
            is_synthetic: boolean;
            /** Name */
            name: string;
        };
        /** ScenarioIn */
        ScenarioIn: {
            /** Assumptions */
            assumptions: components["schemas"]["AssumptionIn"][];
            /** Description */
            description?: string | null;
            /**
             * Kind
             * @enum {string}
             */
            kind: "base" | "upside" | "downside" | "custom";
            /** Name */
            name: string;
            settings: components["schemas"]["ScenarioSettingsIn"];
        };
        /** ScenarioOut */
        ScenarioOut: {
            /** Assumptions */
            assumptions: components["schemas"]["AssumptionOut"][];
            /** Description */
            description: string | null;
            /** Id */
            id: number;
            /** Kind */
            kind: string;
            /** Name */
            name: string;
            /** Project Id */
            project_id: number;
            settings: components["schemas"]["ScenarioSettingsOut"];
        };
        /** ScenarioRunOut */
        ScenarioRunOut: {
            /** Created At */
            created_at: string;
            /** Engine Version */
            engine_version: string;
            /** Id */
            id: number;
            /** Input Hash */
            input_hash: string;
            /** Label */
            label: string | null;
            /** Value Per Share */
            value_per_share: number;
        };
        /** ScenarioSettingsIn */
        ScenarioSettingsIn: {
            /** Debt Value Basis */
            debt_value_basis: ("market" | "book") | null;
            /** Include Leases In Debt */
            include_leases_in_debt: boolean | null;
            /** Market Data Date */
            market_data_date: string | null;
            /** Market Rationale */
            market_rationale?: string | null;
            /** Market Source Id */
            market_source_id?: number | null;
            /** Share Price */
            share_price: number | null;
        };
        /** ScenarioSettingsOut */
        ScenarioSettingsOut: {
            /** Debt Value Basis */
            debt_value_basis: ("market" | "book") | null;
            /** Include Leases In Debt */
            include_leases_in_debt: boolean | null;
            /** Market Data Date */
            market_data_date: string | null;
            /** Market Rationale */
            market_rationale: string | null;
            /** Market Source Id */
            market_source_id: number | null;
            /** Share Price */
            share_price: number | null;
        };
        /** ScenarioUpdateIn */
        ScenarioUpdateIn: {
            /** Assumptions */
            assumptions: components["schemas"]["AssumptionIn"][];
            settings: components["schemas"]["ScenarioSettingsIn"];
        };
        /** SensitivityCellOut */
        SensitivityCellOut: {
            /** Change Abs */
            change_abs: number | null;
            change_pct: components["schemas"]["MetricOut"];
            /** Codes */
            codes: string[];
            /**
             * Status
             * @enum {string}
             */
            status: "ok" | "invalid";
            /** Value */
            value: number | null;
        };
        /** SensitivityIn */
        SensitivityIn: {
            col: components["schemas"]["AxisIn"];
            /**
             * Output
             * @enum {string}
             */
            output: "value_per_share" | "enterprise_value" | "equity_value";
            row: components["schemas"]["AxisIn"];
        };
        /** SensitivityOut */
        SensitivityOut: {
            /** Base Col */
            base_col: number;
            /** Base Matches Run */
            base_matches_run: boolean;
            /** Base Row */
            base_row: number;
            /** Base Value */
            base_value: number;
            /**
             * Basis
             * @constant
             */
            basis: "derived";
            /** Cells */
            cells: components["schemas"]["SensitivityCellOut"][][];
            /** Col Values */
            col_values: number[];
            /** Col Variable */
            col_variable: string;
            context: components["schemas"]["ContextOut"];
            /** Engine Version */
            engine_version: string;
            /** Input Hash */
            input_hash: string;
            /** Output */
            output: string;
            /** Row Values */
            row_values: number[];
            /** Row Variable */
            row_variable: string;
            /** Run Id */
            run_id: number;
        };
        /**
         * Severity
         * @enum {string}
         */
        Severity: "info" | "warning" | "error";
        /** ShareCapitalInputsIn */
        ShareCapitalInputsIn: {
            /** Basic Shares */
            basic_shares: number | null;
            /** Convertibles */
            convertibles: components["schemas"]["ConvertibleInstrumentIn"][];
            /** Options */
            options: components["schemas"]["OptionTrancheIn"][];
            /** Rsus */
            rsus: components["schemas"]["RsuGrantIn"][];
        };
        /**
         * SourceIn
         * @description Analysts can create document sources to back reported values (A4). csv_import and
         *     synthetic sources are created by the system only.
         */
        SourceIn: {
            /**
             * Kind
             * @enum {string}
             */
            kind: "filing" | "market_data";
            /** Notes */
            notes?: string | null;
            /** Reference */
            reference?: string | null;
            /** Title */
            title: string;
            /** Uri */
            uri?: string | null;
        };
        /** SourceOut */
        SourceOut: {
            /** Created At */
            created_at: string;
            /** File Name */
            file_name: string | null;
            /** File Sha256 */
            file_sha256: string | null;
            /** Id */
            id: number;
            /** Kind */
            kind: string;
            /** Notes */
            notes: string | null;
            /** Title */
            title: string;
            /** Uri */
            uri: string | null;
        };
        /**
         * SourceRefIn
         * @description The document a reported correction comes from; stored as a ``filing`` source.
         */
        SourceRefIn: {
            /** Reference */
            reference?: string | null;
            /** Title */
            title: string;
            /** Uri */
            uri?: string | null;
        };
        /**
         * Status
         * @enum {string}
         */
        Status: "ok" | "missing" | "not_meaningful";
        /** TerminalValue */
        TerminalValue: {
            /** Final Ufcf */
            final_ufcf: number;
            /** Growth */
            growth: number;
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /** Value */
            value: number;
            /** Wacc */
            wacc: number;
        };
        /** TokenOut */
        TokenOut: {
            /** Access Token */
            access_token: string;
            /**
             * Expires At
             * Format: date-time
             */
            expires_at: string;
            /**
             * Token Type
             * @default bearer
             * @constant
             */
            token_type: "bearer";
        };
        /** UfcfLine */
        UfcfLine: {
            /** Capex */
            capex: number;
            /** Change In Nwc */
            change_in_nwc: number;
            /** Da */
            da: number;
            /** Ebit */
            ebit: number;
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /** Nopat */
            nopat: number;
            /** T */
            t: number;
            /** Taxes On Ebit */
            taxes_on_ebit: number;
            /** Ufcf */
            ufcf: number;
        };
        /** UserOut */
        UserOut: {
            /** Email */
            email: string;
            /** Id */
            id: number;
        };
        /** ValidationError */
        ValidationError: {
            /** Context */
            ctx?: Record<string, never>;
            /** Input */
            input?: unknown;
            /** Location */
            loc: (string | number)[];
            /** Message */
            msg: string;
            /** Error Type */
            type: string;
        };
        /** ValuationDatesIn */
        ValuationDatesIn: {
            /**
             * Market Data Date
             * Format: date
             */
            market_data_date: string;
            /**
             * Statement Date
             * Format: date
             */
            statement_date: string;
            /**
             * Valuation Date
             * Format: date
             */
            valuation_date: string;
        };
        /** VerifyOut */
        VerifyOut: {
            /** Differing Paths */
            differing_paths: string[];
            /** Engine Version At Run */
            engine_version_at_run: string;
            /** Engine Version Changed */
            engine_version_changed: boolean;
            /** Engine Version Now */
            engine_version_now: string;
            /** Identical */
            identical: boolean;
            /** Input Hash Matches */
            input_hash_matches: boolean;
            /** Inputs Round Trip Exact */
            inputs_round_trip_exact: boolean;
            /** Run Id */
            run_id: number;
            value_per_share: components["schemas"]["VerifyValuesOut"];
        };
        /** VerifyValuesOut */
        VerifyValuesOut: {
            /** Recomputed */
            recomputed: number;
            /** Stored */
            stored: number;
        };
        /** WaccAssumptionsIn */
        WaccAssumptionsIn: {
            /** Cost Of Preferred */
            cost_of_preferred: number | null;
            debt_value_basis: components["schemas"]["DebtValueBasis"] | null;
            /** Equity Risk Premium */
            equity_risk_premium: number | null;
            /** Levered Beta */
            levered_beta: number | null;
            /** Pre Tax Cost Of Debt */
            pre_tax_cost_of_debt: number | null;
            /** Risk Free Rate */
            risk_free_rate: number | null;
            /** Size Premium */
            size_premium: number | null;
            /** Target Debt To Capital */
            target_debt_to_capital: number | null;
        };
        /** WaccResult */
        WaccResult: {
            /** After Tax Cost Of Debt */
            after_tax_cost_of_debt: number;
            /** Cost Of Equity */
            cost_of_equity: number;
            /** Cost Of Preferred */
            cost_of_preferred: number | null;
            /** Issues */
            issues: components["schemas"]["Issue"][];
            /** Wacc */
            wacc: number;
            /** Weight Debt */
            weight_debt: number;
            /** Weight Equity */
            weight_equity: number;
            /** Weight Preferred */
            weight_preferred: number;
        };
    };
    responses: never;
    parameters: never;
    requestBodies: never;
    headers: never;
    pathItems: never;
}
export type $defs = Record<string, never>;
export interface operations {
    logout_api_v1_auth_logout_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            204: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    me_api_v1_auth_me_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
        };
    };
    register_api_v1_auth_register_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RegisterIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["UserOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    token_api_v1_auth_token_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LoginIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["TokenOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    calculate_dcf_api_v1_calculate_dcf_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["DcfInputsIn"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DcfResult"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_companies_api_v1_companies_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CompanyOut"][];
                };
            };
        };
    };
    create_company_api_v1_companies_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CompanyIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CompanyOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_company_api_v1_companies__company_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                company_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["CompanyOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_financials_api_v1_companies__company_id__financials_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                company_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["FinancialsOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    import_financials_api_v1_companies__company_id__financials_import_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                company_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "multipart/form-data": components["schemas"]["Body_import_financials_api_v1_companies__company_id__financials_import_post"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ImportOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_historical_analysis_api_v1_companies__company_id__historical_analysis_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                company_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HistoricalAnalysisOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_instruments_api_v1_companies__company_id__share_instruments_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                company_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstrumentOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    put_instruments_api_v1_companies__company_id__share_instruments_put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                company_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["InstrumentsIn"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["InstrumentsPutOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_dashboard_api_v1_dashboard_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["DashboardOut"];
                };
            };
        };
    };
    health_api_v1_health_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HealthOut"];
                };
            };
        };
    };
    line_item_dictionary_api_v1_line_items_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["LineItemDefOut"][];
                };
            };
        };
    };
    patch_line_item_api_v1_line_items__line_item_id__patch: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                line_item_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["LineItemPatchIn"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PatchLineItemOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_projects_api_v1_projects_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"][];
                };
            };
        };
    };
    create_project_api_v1_projects_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ProjectIn"];
            };
        };
        responses: {
            /** @description Successful Response */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_project_api_v1_projects__project_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Successful Response */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ProjectOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_scenarios_api_v1_projects__project_id__scenarios_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_scenario_api_v1_projects__project_id__scenarios_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                project_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScenarioIn"];
            };
        };
        responses: {
            /** @description Success */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_all_runs_api_v1_runs_get: {
        parameters: {
            query?: {
                page?: number;
                page_size?: number;
                company_id?: number | null;
                project_id?: number | null;
                scenario_id?: number | null;
            };
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunsPageOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_run_api_v1_runs__run_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    run_sensitivity_api_v1_runs__run_id__sensitivity_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SensitivityIn"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SensitivityOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    verify_run_api_v1_runs__run_id__verify_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                run_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["VerifyOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_samples_api_v1_samples_get: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SampleOut"][];
                };
            };
        };
    };
    load_sample_api_v1_samples__sample_id__load_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                sample_id: string;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SampleLoadOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_scenario_api_v1_scenarios__scenario_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    update_scenario_api_v1_scenarios__scenario_id__put: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["ScenarioUpdateIn"];
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    clone_scenario_api_v1_scenarios__scenario_id__clone_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["CloneIn"];
            };
        };
        responses: {
            /** @description Success */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    preview_api_v1_scenarios__scenario_id__preview_post: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody?: {
            content: {
                "application/json": components["schemas"]["ScenarioUpdateIn"] | null;
            };
        };
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["PreviewOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    list_runs_api_v1_scenarios__scenario_id__runs_get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["ScenarioRunOut"][];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    create_run_api_v1_scenarios__scenario_id__runs_post: {
        parameters: {
            query?: never;
            header: {
                /** @description Mandatory (A7). A new random key per user action; reuse it to retry. */
                "Idempotency-Key": string;
            };
            path: {
                scenario_id: number;
            };
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["RunIn"];
            };
        };
        responses: {
            /** @description Replay: this Idempotency-Key already froze this request; the same run is returned (header Idempotent-Replayed: true). */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description The new frozen run. */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["RunOut"];
                };
            };
            /** @description IDEMPOTENCY_KEY_REUSED: the key was used for another request. */
            409: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
            /** @description DATABASE_BUSY: nothing saved; retry with the same key. */
            503: {
                headers: {
                    [name: string]: unknown;
                };
                content?: never;
            };
        };
    };
    create_source_api_v1_sources_post: {
        parameters: {
            query?: never;
            header?: never;
            path?: never;
            cookie?: never;
        };
        requestBody: {
            content: {
                "application/json": components["schemas"]["SourceIn"];
            };
        };
        responses: {
            /** @description Success */
            201: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
    get_source_api_v1_sources__source_id__get: {
        parameters: {
            query?: never;
            header?: never;
            path: {
                source_id: number;
            };
            cookie?: never;
        };
        requestBody?: never;
        responses: {
            /** @description Success */
            200: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["SourceOut"];
                };
            };
            /** @description Validation Error */
            422: {
                headers: {
                    [name: string]: unknown;
                };
                content: {
                    "application/json": components["schemas"]["HTTPValidationError"];
                };
            };
        };
    };
}
