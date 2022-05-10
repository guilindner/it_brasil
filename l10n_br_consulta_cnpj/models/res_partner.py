from datetime import datetime
import json
import re
import logging

import requests

from odoo import models, _, fields
from odoo.exceptions import ValidationError, UserError


_logger = logging.getLogger(__name__)


class Partner(models.Model):
    _name = "res.partner"
    _inherit = [_name, "l10n_br_base.party.mixin"]

    cnpjws_atualizadoem = fields.Datetime(
        string="Atualizado na base pública em",
        help="Data da última atualização das informações",
        readonly=True,
        copy=False
    )
    cnpjws_nome_fantasia = fields.Char(
        string="Nome Fantasia",
        readonly=True,
        copy=False
    )
    cnpjws_situacao_cadastral = fields.Char(
        string="Situação Cadastral",
        readonly=True,
        copy=False
    )
    cnpjws_tipo = fields.Char(
        string="Tipo de Empresa",
        readonly=True,
        copy=False
    )

    cnpjws_porte = fields.Char(
        string="Porte",
        readonly=True,
        copy=False
    )

    cnpjws_atualizado_odoo = fields.Datetime(
        string="Atualizado no Odoo em",
        help="Data da última atualização das informações no Odoo",
        readonly=True,
        copy=False
    )

    def action_consult_cnpj(self):
        cnpjws_url = 'https://publica.cnpj.ws/cnpj/'
        if self.company_type == 'company':
            if self.cnpj_cpf:
                cnpj = re.sub('[^0-9]', '', self.cnpj_cpf)
                response = requests.get(cnpjws_url + cnpj)
                cnpjws_result = json.loads(response.text)
                if response.status_code == 200:
                    self.legal_name = cnpjws_result['razao_social']

                    cnpjws_estabelecimento = cnpjws_result['estabelecimento']
                    cnpjws_pais = cnpjws_result['estabelecimento']['pais']['comex_id']
                    cnpjws_estado = cnpjws_estabelecimento['estado']
                    cnpjws_cidade = cnpjws_estabelecimento['cidade']

                    search_country = self.env['res.country'].search(
                        [('siscomex_code', '=', cnpjws_pais)])
                    if search_country:
                        self.country_id = search_country.id

                    if cnpjws_estado['ibge_id']:
                        search_state = self.env['res.country.state'].search(
                            [('ibge_code', '=', cnpjws_estado['ibge_id'])])
                        if search_state:
                            self.state_id = search_state.id

                    if cnpjws_cidade:
                        self.city = cnpjws_cidade['nome']
                        search_city = self.env['res.city'].search(
                            [('ibge_code', '=', cnpjws_cidade['ibge_id'])])
                        if search_city:
                            self.city_id = search_city.id

                    self.zip = cnpjws_estabelecimento['cep']

                    if cnpjws_estabelecimento['tipo_logradouro']:
                        cnpj_t_logra = cnpjws_estabelecimento['tipo_logradouro']
                        cnpj_logra = cnpjws_estabelecimento['logradouro']

                        self.street_name = cnpj_t_logra + " " + cnpj_logra

                    self.street_number = cnpjws_estabelecimento['numero']

                    self.district = cnpjws_estabelecimento['bairro']
                    self.street2 = cnpjws_estabelecimento['complemento']

                    cnpjws_simples = cnpjws_result['simples']
                    cnpjws_ie = cnpjws_estabelecimento['inscricoes_estaduais']
                    cnpjws_cnae = cnpjws_estabelecimento['atividade_principal']

                    fiscal_info = []

                    fiscal_info.append(cnpjws_simples)
                    fiscal_info.append(cnpjws_ie)
                    fiscal_info.append(cnpjws_cnae)

                    self.define_fiscal_profile_id(fiscal_info)
                    self.cnpjws_atualizadoem = datetime.strptime(cnpjws_result['atualizado_em'], '%Y-%m-%dT%H:%M:%S.%fZ')
                    self.cnpjws_nome_fantasia = cnpjws_estabelecimento['nome_fantasia']
                    self.cnpjws_tipo = cnpjws_estabelecimento['tipo']
                    self.cnpjws_situacao_cadastral = cnpjws_estabelecimento['situacao_cadastral']
                    self.cnpjws_porte = cnpjws_result['porte']['descricao']
                    self.cnpjws_atualizado_odoo = datetime.now()
                else:
                    raise ValidationError(
                        "Erro: " + cnpjws_result['titulo'] + '\n' + cnpjws_result['detalhes'] + '\n' 'Se a empresa for do Brasil, informe o CNPJ correto. Caso contrário, complete o cadastro manualmente.')
            else:
                raise UserError("Por favor, informe o CNPJ da empresa.")
        else:
            raise ValidationError(
                "Apenas contatos do tipo Empresa com CNPJ podem ser consultados.")

    def define_inscricao_estadual(self, fiscal_info):
        result_ie = fiscal_info[1]

        if result_ie == []:
            self.inscr_est = ''
        else:
            if len(result_ie) == 1:
                if result_ie[0]['ativo'] == True:
                    self.inscr_est = result_ie[0]['inscricao_estadual']
                else:
                    self.inscr_est = ''
            elif len(result_ie) == 2:
                if result_ie[0]['ativo'] == True:
                    if self.state_id.code == result_ie[0]['estado']['sigla']:
                        self.inscr_est = result_ie[0]['inscricao_estadual']

                        if result_ie[1]['ativo'] == True:
                            search_state = self.env['res.country.state'].search(
                                [('ibge_code', '=', result_ie[1]['estado']['ibge_id'])])
                            if search_state:
                                try:
                                    incluir_segunda_ie = self.write(
                                        {"state_tax_number_ids": [(0, 0, {
                                            "state_id": search_state.id,
                                            "inscr_est": result_ie[1]['inscricao_estadual']
                                        })]}
                                    )
                                    _logger.warning(incluir_segunda_ie)
                                except Exception:
                                    incluir_segunda_ie = False
                                    raise ValidationError(
                                        "Erro ao incluir segunda inscrição estadual: %s estado %s", result_ie[1]['inscricao_estadual'], result_ie[1]['estado']['sigla'])
                    else:
                        if result_ie[1]['ativo'] == True:
                            if self.state_id.code == result_ie[1]['estado']['sigla']:
                                self.inscr_est = result_ie[1]['inscricao_estadual']

                                if result_ie[0]['ativo'] == True:
                                    search_state = self.env['res.country.state'].search(
                                        [('ibge_code', '=', result_ie[0]['estado']['ibge_id'])])
                                if search_state:
                                    try:
                                        incluir_segunda_ie = self.write(
                                            {"state_tax_number_ids": [(0, 0, {
                                                "state_id": search_state.id,
                                                "inscr_est": result_ie[0]['inscricao_estadual']
                                            })]}
                                        )
                                        _logger.warning(incluir_segunda_ie)
                                    except Exception:
                                        incluir_segunda_ie = False
                                        raise ValidationError(
                                            "Erro ao incluir segunda inscrição estadual: %s estado %s", result_ie[1]['inscricao_estadual'], result_ie[1]['estado']['sigla'])
                            else:
                                _logger.warning(
                                    "Estado %s está divergente", self.state_id.name)
                else:
                    if self.state_id.code == result_ie[1]['estado']['sigla']:
                        self.inscr_est = result_ie[1]['inscricao_estadual']
                    else:
                        _logger.warning("Estado %s está divergente",
                                        self.state_id.name)
            else:
                _logger.warning("TEM %s IES", len(result_ie))
                raise ValidationError(
                    "O CNPJ %s tem %s Inscrições Estaduais, necessário avisar o time de desenvolvimento", self.cnpj_cpf, len(result_ie))

    def define_fiscal_profile_id(self, fiscal_info):
        module_l10n_br_fiscal = self.env['ir.module.module'].search(
            [('name', '=', 'l10n_br_fiscal'), ('state', '=', 'installed')])

        result_simples = fiscal_info[0]

        if module_l10n_br_fiscal:
            # SNC - Contribuinte Simples Nacional
            # SNN - Simples Nacional Não Contribuinte
            # CNT - Contribuinte
            # NCN - Não Contribuinte
            search_fiscal_profile_id = self.env["l10n_br_fiscal.partner.profile"]

            profile_snc = search_fiscal_profile_id.search([('code', '=', 'SNC')]).id
            profile_snn = search_fiscal_profile_id.search([('code', '=', 'SNN')]).id
            profile_cnt = search_fiscal_profile_id.search([('code', '=', 'CNT')]).id
            profile_ncn = search_fiscal_profile_id.search([('code', '=', 'NCN')]).id

            self.define_inscricao_estadual(fiscal_info)
            contribuinte_icms = False
            if self.inscr_est:
                contribuinte_icms = True

            simples_nacional = False
            if result_simples:
                if result_simples['simples'] == 'Sim' or result_simples['mei'] == 'Sim':
                    simples_nacional = True

            if contribuinte_icms and result_simples:
                if simples_nacional:
                    self.fiscal_profile_id = profile_snc
                else:
                    self.fiscal_profile_id = profile_cnt
            elif not contribuinte_icms and result_simples:
                if simples_nacional:
                    self.fiscal_profile_id = profile_snn
                else:
                    self.fiscal_profile_id = profile_ncn
            elif contribuinte_icms and not result_simples:
                self.fiscal_profile_id = profile_cnt
            elif not contribuinte_icms and not result_simples:
                self.fiscal_profile_id = profile_ncn

            if fiscal_info[2]:
                search_cnae = self.env["l10n_br_fiscal.cnae"].search(
                    [('code', '=', fiscal_info[2]['subclasse'])])

                if search_cnae:
                    try:
                        incluir_cnae_principal = self.write(
                            {"cnae_main_id": search_cnae.id})
                        _logger.warning(incluir_cnae_principal)
                    except Exception:
                        incluir_cnae_principal = False
                        raise ValidationError(
                            "Erro ao incluir cnae: %s", fiscal_info[2]['subclasse'])

        else:
            self.define_inscricao_estadual(fiscal_info)
